import google.generativeai as genai

# Your API key is pasted here
GEMINI_API_KEY = "AIzaSyB57cj-I9aVGJKlp_0pzyW3R4wpl5_aDDM"

try:
    genai.configure(api_key=GEMINI_API_KEY)

    print("Successfully connected to Google AI.")
    print("Finding all available models for your key...")
    print("---------------------------------------------")

    for model in genai.list_models():
        # We check if the model supports the 'generateContent' method
        if 'generateContent' in model.supported_generation_methods:
            print(f"Model Name: {model.name}")
            
    print("---------------------------------------------")
    print("Please copy the 'Model Name' (e.g., 'gemini-pro') from this list and paste it in the chat.")

except Exception as e:
    print(f"An error occurred: {e}")
    print("This is likely an API key or internet connection issue.")