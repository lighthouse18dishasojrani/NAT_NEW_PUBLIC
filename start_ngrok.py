from pyngrok import ngrok  
public_url = ngrok.connect(8000)
print(f"🔗 Public URL: {public_url}")
input("Press Enter to stop tunnel...")
