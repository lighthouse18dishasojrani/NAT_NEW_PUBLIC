from pyngrok import installer
import os

# Where we want ngrok.exe to live
ngrok_dir = os.path.expanduser("~/.ngrok2")
os.makedirs(ngrok_dir, exist_ok=True)   # ✅ Create folder if missing

ngrok_path = os.path.join(ngrok_dir, "ngrok.exe")

# Install ngrok into that path
installer.install_ngrok(ngrok_path)

print(f"✅ ngrok installed at {ngrok_path}")
