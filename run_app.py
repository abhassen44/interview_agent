import os
import subprocess
import sys
import time
from pathlib import Path

def run_backend():
    print("Starting FastAPI backend...")
    backend_process = subprocess.Popen(
        [sys.executable, "run_api.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return backend_process

def run_frontend():
    print("Starting React frontend...")
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print(f"Error: Frontend directory '{frontend_dir}' not found.")
        return None
    
    # Use npm or yarn depending on what's available
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    
    frontend_process = subprocess.Popen(
        [npm_cmd, "start"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return frontend_process

def monitor_processes(processes):
    try:
        while all(p.poll() is None for p in processes if p is not None):
            for p in processes:
                if p is not None and p.poll() is None:
                    line = p.stdout.readline()
                    if line:
                        print(line.strip())
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping all processes...")
        for p in processes:
            if p is not None and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()

def main():
    print("Starting Interview Agent Application...")
    
    # Check if virtual environment is activated
    if not os.environ.get("VIRTUAL_ENV"):
        print("Warning: Virtual environment not detected. It's recommended to run this script within a virtual environment.")
    
    # Start backend and frontend
    backend_process = run_backend()
    time.sleep(2)  # Give backend time to start
    frontend_process = run_frontend()
    
    # Monitor and display output from both processes
    monitor_processes([p for p in [backend_process, frontend_process] if p is not None])

if __name__ == "__main__":
    main()