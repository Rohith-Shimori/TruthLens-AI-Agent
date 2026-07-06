import subprocess
import re
import time
import os
import sys

def update_repo_links(new_url):
    print(f"[Watchdog] Updating repository links to: {new_url}")
    
    # Update README.md
    readme_path = "README.md"
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Handle both bolding formats (* and **)
        updated = re.sub(
            r"\*\s+\*\*Live Web Demo:\*\*\s+https://[a-zA-Z0-9\-]+\.gradio\.live",
            f"*   **Live Web Demo:** {new_url}",
            content
        )
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(updated)
            
    # Update docs/kaggle_writeup.md
    writeup_path = os.path.join("docs", "kaggle_writeup.md")
    if os.path.exists(writeup_path):
        with open(writeup_path, "r", encoding="utf-8") as f:
            content = f.read()
        updated = re.sub(
            r"\*\s+\*\*Interactive Demo Link:\*\*\s+https://[a-zA-Z0-9\-]+\.gradio\.live\s+\(Live Web Demo\)",
            f"*   **Interactive Demo Link:** {new_url} (Live Web Demo)",
            content
        )
        with open(writeup_path, "w", encoding="utf-8") as f:
            f.write(updated)
            
    # Commit and push changes
    try:
        subprocess.run(["git", "add", "README.md", "docs/kaggle_writeup.md"], check=True)
        subprocess.run(["git", "commit", "-m", "Auto: Update live Gradio demo URL [skip ci]"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("[Watchdog] Successfully pushed updated links to GitHub!")
    except Exception as e:
        print(f"[Watchdog] Git commit/push failed: {e}")

def run_app():
    # 70 hours in seconds
    max_runtime = 70 * 3600
    start_time = time.time()
    
    # Run app.py with unbuffered python
    print("[Watchdog] Starting app.py...")
    process = subprocess.Popen(
        [sys.executable, "-u", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Read stdout in real-time
    url_pattern = re.compile(r"Running on public URL:\s*(https://[a-zA-Z0-9\-]+\.gradio\.live)")
    
    for line in iter(process.stdout.readline, ""):
        print(line, end="")
        match = url_pattern.search(line)
        if match:
            new_url = match.group(1)
            update_repo_links(new_url)
            
        # Check if we need to restart due to 70 hours runtime limit
        if time.time() - start_time > max_runtime:
            print("[Watchdog] Max runtime reached (70 hours). Restarting process to refresh link...")
            process.terminate()
            break
            
    process.wait()
    print("[Watchdog] app.py terminated.")

def main():
    while True:
        try:
            run_app()
        except KeyboardInterrupt:
            print("[Watchdog] Shutting down...")
            break
        except Exception as e:
            print(f"[Watchdog] Error in run loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
