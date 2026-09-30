import os
import re
from google import genai

# Fetch API Key and Tracking ID from GitHub Repository Secrets
API_KEY = os.environ.get("GEMINI_API_KEY")
AMAZON_ID = os.environ.get("AMAZON_TRACKING_ID", "default-20")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is missing.")

# Initialize the Gemini API client
client = genai.Client(api_key=API_KEY)

# Define target programmatic topics/keywords
topics = [
    "Best Data Scraping Tools for E-commerce Price Monitoring",
    "Top Enterprise Cloud Hosting Solutions for WooCommerce",
    "Commercial General Liability Insurance Requirements for Small Contractors"
]

def sanitize_filename(title):
    """Converts a title string into a safe filename."""
    clean = re.sub(r'[^\w\s-]', '', title).strip().lower()
    return re.sub(r'[-\s]+', '-', clean) + ".md"

def generate_content(topic):
    """Prompts Gemini to generate a structured, SEO-optimized markdown article."""
    prompt = f"""
    Write an authoritative, highly structured buyer guide in Markdown format for the topic: "{topic}".
    
    Structure Requirements:
    - Include a clear title (# Header).
    - Provide a short summary section.
    - Create a comparison breakdown using bullet points or Markdown tables.
    - Highlight recommended tools/services.
    - End with a call to action mentioning checking current pricing on Amazon or official vendor partners using tag: {AMAZON_ID}.
    - Ensure clear FTC affiliate disclosures at the top.
    """
    
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt
    )
    return response.text

def main():
    # Ensure content directory exists
    output_dir = "content"
    os.makedirs(output_dir, exist_ok=True)
    
    for topic in topics:
        filename = sanitize_filename(topic)
        filepath = os.path.join(output_dir, filename)
        
        # Skip generation if file already exists to prevent duplicate runs
        if os.path.exists(filepath):
            print(f"Skipping (already exists): {filepath}")
            continue
            
        print(f"Generating content for: {topic}...")
        markdown_content = generate_content(topic)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        print(f"Saved: {filepath}")

if __name__ == "__main__":
    main()
