import requests
from bs4 import BeautifulSoup
import wikipediaapi
from typing import List, Dict, Any, Optional
import os
import urllib.parse
from PIL import Image
from google import genai
from google.genai import types
from config import GOOGLE_API_KEY, DEFAULT_MODEL

# Initialize Wikipedia API
# Using a descriptive user_agent as required by Wikipedia policy
wiki = wikipediaapi.Wikipedia(
    language='en',
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent="TruthLensFactChecker/1.0 (contact: capstone-project@truthlens.ai)"
)

def get_genai_client() -> Optional[genai.Client]:
    """Helper to initialize the Google GenAI client."""
    api_key = GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error initializing GenAI Client: {e}")
        return None

def scrape_url(url: str) -> Dict[str, Any]:
    """Scrapes the text content and metadata from a URL."""
    if not url:
        return {"error": "Empty URL"}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get title
        title = soup.title.string.strip() if soup.title else ""
        
        # Get main content (paragraphs)
        paragraphs = [p.get_text().strip() for p in soup.find_all('p') if p.get_text().strip()]
        content = "\n\n".join(paragraphs[:15])  # Limit size
        
        return {
            "title": title,
            "content": content[:8000],  # Truncate to fit context
            "url": url
        }
    except Exception as e:
        return {"error": f"Failed to scrape URL {url}: {str(e)}", "url": url}

def search_wikipedia(query: str) -> List[Dict[str, Any]]:
    """Searches Wikipedia for matching pages and retrieves summaries."""
    if not query:
        return []
    
    try:
        # Search page matching
        page = wiki.page(query)
        if page.exists():
            return [{
                "title": page.title,
                "summary": page.summary[:1500],
                "url": page.fullurl,
                "source": "Wikipedia"
            }]
        
        # Try a broader search via API directly
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1
        }
        res = requests.get(search_url, params=params, timeout=5).json()
        search_results = res.get("query", {}).get("search", [])
        
        ret = []
        for item in search_results[:3]:
            title = item.get("title")
            p = wiki.page(title)
            if p.exists():
                ret.append({
                    "title": p.title,
                    "summary": p.summary[:1000],
                    "url": p.fullurl,
                    "source": "Wikipedia"
                })
        return ret
    except Exception as e:
        print(f"Wikipedia search failed for '{query}': {e}")
        return []

def search_duckduckgo(query: str) -> List[Dict[str, Any]]:
    """Searches DuckDuckGo HTML interface as a fallback scraping method."""
    if not query:
        return []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        response = requests.get(url, headers=headers, timeout=8)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # DuckDuckGo HTML elements
        for a in soup.find_all('a', class_='result__snippet')[:5]:
            parent = a.find_parent('div', class_='result__body')
            if parent:
                title_elem = parent.find('a', class_='result__url')
                if title_elem:
                    title = title_elem.get_text().strip()
                    href = title_elem.get('href', '')
                    
                    # Clean DuckDuckGo redirect URLs
                    if href.startswith("/l/?kh=-1&uddg="):
                        redirect_part = href.split("uddg=")[1]
                        href = urllib.parse.unquote(redirect_part)
                    
                    snippet = a.get_text().strip()
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": href,
                        "source": "DuckDuckGo"
                    })
        return results
    except Exception as e:
        print(f"DuckDuckGo search failed for '{query}': {e}")
        return []

def search_google_grounding(query: str) -> List[Dict[str, Any]]:
    """Uses Gemini API's built-in Google Search grounding capability."""
    client = get_genai_client()
    if not client:
        # Fallback to DuckDuckGo search if client cannot be initialized
        return search_duckduckgo(query)
    
    try:
        # Define Google Search tool
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        config = types.GenerateContentConfig(
            tools=[google_search_tool],
            temperature=0.1
        )
        
        prompt = f"Retrieve facts and sources for the following query: {query}. List the key facts and their sources with URLs."
        
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt,
            config=config
        )
        
        # Extract grounding metadata if available
        candidates = response.candidates
        grounding_metadata = None
        if candidates and len(candidates) > 0:
            grounding_metadata = candidates[0].grounding_metadata
            
        results = []
        if grounding_metadata and grounding_metadata.grounding_chunks:
            for chunk in grounding_metadata.grounding_chunks:
                web = chunk.web
                if web:
                    results.append({
                        "title": web.title,
                        "snippet": response.text[:500],  # Use response summary
                        "url": web.uri,
                        "source": "Google Grounded Search"
                    })
                    
        # If no explicit metadata chunks, parse response text
        if not results:
            results.append({
                "title": "Google Search Grounding Synthesis",
                "snippet": response.text,
                "url": "https://google.com",
                "source": "Google Grounded Search"
            })
            
        return results
    except Exception as e:
        print(f"Google grounding search failed: {e}. Falling back to DuckDuckGo.")
        return search_duckduckgo(query)

def extract_text_from_image(image_path: str) -> Dict[str, Any]:
    """Uses Gemini Vision capability to perform OCR and analyze an image for claim extraction."""
    client = get_genai_client()
    if not client:
        return {"error": "Gemini API key is missing or invalid. OCR tool unavailable."}
        
    if not os.path.exists(image_path):
        return {"error": f"Image file not found: {image_path}"}
        
    try:
        img = Image.open(image_path)
        
        prompt = (
            "Perform high-precision OCR on this image. Extract all readable text. "
            "Then, identify if the image is a social media post, a chat message (like WhatsApp or Telegram), "
            "a news screenshot, or a meme. Describe any visual context, logos, or figures "
            "that could be relevant to fact-checking. Format your response clearly."
        )
        
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[img, prompt]
        )
        
        return {
            "text": response.text,
            "image_type": "Processed image",
            "metadata": {
                "format": img.format,
                "size": img.size
            }
        }
    except Exception as e:
        return {"error": f"Failed to analyze image with Gemini: {str(e)}"}
