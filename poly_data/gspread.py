import gspread
from google.oauth2.service_account import Credentials
import os
from dotenv import load_dotenv
import pandas as pd
import json

load_dotenv()

def get_spreadsheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet_url = os.getenv("SPREADSHEET_URL")
        if not spreadsheet_url:
            return None
        return client.open_by_url(spreadsheet_url)
    except Exception as e:
        print(f"Warning: Could not connect to Google Sheets ({e}). Returning None.")
        return None

def test_gspread():
    try:
        sheet = get_spreadsheet()
        print(f"Spreadsheet: {sheet.title}")
        for ws in ["Selected Markets", "All Markets", "Hyperparameters"]:
            try:
                worksheet = sheet.worksheet(ws)
                # Debug raw headers
                raw_headers = worksheet.row_values(1) or []
                print(f"{ws} raw headers: {raw_headers}")
                df = pd.DataFrame(worksheet.get_all_records())
                print(f"{ws} Columns: {list(df.columns)}")
                print(f"{ws} Data (rows: {len(df)}): {df if not df.empty else 'Empty'}")
                # Test write access
                if df.empty:
                    worksheet.update_cell(2, 1, "TestWrite")
                    print(f"Successfully wrote to {ws} (row 2, column 1)")
                    worksheet.update_cell(2, 1, "")
                else:
                    print(f"Skipped write test for {ws} (non-empty data)")
            except gspread.exceptions.WorksheetNotFound:
                print(f"Error: '{ws}' worksheet not found. Create it with appropriate headers.")
            except gspread.exceptions.APIError as e:
                print(f"Error: Failed to write to {ws}. Check Edit permissions: {str(e)}")
        # Print Service Account email
        try:
            with open("credentials.json") as f:
                creds = json.load(f)
                print(f"Service Account Email: {creds['client_email']}")
        except Exception as e:
            print(f"Error reading credentials.json: {str(e)}")
    except gspread.exceptions.SpreadsheetNotFound:
        print("Error: Spreadsheet not found. Check SPREADSHEET_URL or permissions.")
    except FileNotFoundError:
        print("Error: credentials.json not found in project root.")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_gspread()