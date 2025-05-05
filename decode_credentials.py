import base64
import os

def decode_base64_to_file(encoded_string, output_file):
    """Decodes a Base64 encoded string and writes it to a file."""
    if not encoded_string:
        raise ValueError("Encoded string is empty or None.")

    # Clean up unwanted characters
    encoded_string = encoded_string.strip().replace('\n', '')

    # Ensure proper padding
    encoded_string = encoded_string.rstrip('=')
    encoded_string += '=' * (-len(encoded_string) % 4)

    try:
        decoded_data = base64.b64decode(encoded_string, validate=False)
    except Exception as e:
        raise ValueError(f"Base64 decoding failed: {e}")

    try:
        with open(output_file, 'wb') as f:
            f.write(decoded_data)
    except IOError as e:
        raise ValueError(f"Failed to write to file '{output_file}': {e}")

    print(f"[✓] Successfully decoded and saved to {output_file}")
