import base64
import os

def decode_base64_to_file(encoded_string, output_file):
    """Decodes a Base64 encoded string and writes it to a file."""
    # Clean up the string
    encoded_string = encoded_string.strip().replace('\n', '')

    # Fix padding if needed
    padding_needed = 4 - (len(encoded_string) % 4)
    if padding_needed and padding_needed != 4:
        encoded_string += '=' * padding_needed

    try:
        decoded_data = base64.b64decode(encoded_string)
    except Exception as e:
        raise ValueError(f"Base64 decoding failed: {e}")

    with open(output_file, 'wb') as f:
        f.write(decoded_data)

def main():
    google_credentials = os.getenv("GOOGLE_CREDENTIALS_JSON")
    google_token = os.getenv("GOOGLE_TOKEN_JSON")

    if not google_credentials or not google_token:
        raise ValueError("Google credentials or token are missing from environment variables.")

    decode_base64_to_file(google_credentials, 'google_credentials.json')
    decode_base64_to_file(google_token, 'google_token.json')
    print("[✓] Google credentials and token decoded successfully.")

if __name__ == "__main__":
    main()
