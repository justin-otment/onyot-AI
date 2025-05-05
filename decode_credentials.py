import base64
import os

def decode_base64_to_file(encoded_string, output_file):
    """Decodes a Base64 encoded string and writes it to a file."""
    # Fix padding only if necessary
    missing_padding = len(encoded_string) % 4
    if missing_padding:
        encoded_string += '=' * (4 - missing_padding)
    
    with open(output_file, 'wb') as f:
        f.write(base64.b64decode(encoded_string))

def main():
    google_credentials = os.getenv("GOOGLE_CREDENTIALS_JSON")
    google_token = os.getenv("GOOGLE_TOKEN_JSON")

    if not google_credentials or not google_token:
        raise ValueError('Google credentials or token are missing.')

    decode_base64_to_file(google_credentials, 'google_credentials.json')
    decode_base64_to_file(google_token, 'google_token.json')
    print("[✓] Google credentials and token have been decoded and saved.")

if __name__ == "__main__":
    main()
