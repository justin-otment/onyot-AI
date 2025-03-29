import pandas as pd
import csv
import re

def clean_email(email):
    """
    Remove HTML tags from an email string.
    """
    clean = re.compile('<.*?>')
    return re.sub(clean, '', email)

def process_data(input_file, output_file):
    """
    Process the input CSV file, clean and transform the data, 
    and save the output to a new CSV file.
    """
    # Read the input CSV file
    with open(input_file, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        input_data = list(reader)

    # List to store the processed rows
    output_data = []

    # Process each row in the input data
    for row in input_data:
        address = row.get('Address', '')
        first_name = row.get('First Name', '')
        last_name = row.get('Last Name', '')

        # Extract phone numbers and phone types
        phone_numbers = [
            row.get(f'Phone {i}', '') for i in range(1, 6) if row.get(f'Phone {i}', '')
        ]
        phone_types = [
            row.get(f'Phone Type {i}', '') for i in range(1, 6) if row.get(f'Phone Type {i}', '')
        ]

        # Extract and clean email addresses
        emails = [
            clean_email(row.get(f'Email {i}', '')) for i in range(1, 4) if row.get(f'Email {i}', '')
        ]

        # Calculate the maximum number of rows needed for this record
        max_rows = max(len(phone_numbers), len(phone_types), len(emails))

        # Append the processed data to the output list
        for i in range(max_rows):
            output_data.append({
                'Address': address,
                'First Name': first_name,
                'Last Name': last_name,
                'Phone Number': phone_numbers[i] if i < len(phone_numbers) else '',
                'Phone Type': phone_types[i] if i < len(phone_types) else '',
                'Email': emails[i] if i < len(emails) else ''
            })

    # Convert the processed data to a DataFrame
    output_df = pd.DataFrame(output_data)

    # Save the processed data to the output CSV file
    output_df.to_csv(output_file, index=False)

# Define file paths
input_file = "C:\\Users\\DELL\\Documents\\Onyot.ai\\Lead_List-Generator\\python tests\\arcGIS_cape2.csv"
output_file = "C:\\Users\\DELL\\Documents\\Onyot.ai\\Lead_List-Generator\\python tests\\arcGIS_cape2_processed.csv"

# Main execution
if __name__ == "__main__":
    process_data(input_file, output_file)
    print(f"Processed data has been saved to {output_file}")
