# TG Cleaner Pro

A professional Telegram group and channel cleaner web application that helps users efficiently manage and leave unwanted groups in bulk.

## Features

- **Secure Login**: Authenticate using your Telegram phone number and OTP
- **Smart Selection**: Choose which groups/channels to keep
- **Bulk Cleanup**: Automatically leave multiple groups at once
- **Progress Tracking**: Real-time progress updates during cleanup
- **2FA Support**: Handles two-factor authentication
- **Flood Protection**: Built-in delays to prevent Telegram rate limits

## Setup

1. **Clone or download** the project files
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure environment**:
   - Create a `.env` file in the root directory
   - Add your Telegram API credentials:
     ```
     API_ID=your_api_id
     API_HASH=your_api_hash
     ```
   - Get these from [Telegram API](https://my.telegram.org/auth)

4. **Run the application**:
   ```bash
   uvicorn main:app --reload
   ```

5. **Open your browser** and go to `http://localhost:8000`

## Usage

1. Enter your phone number in international format (+947XXXXXXXX)
2. Enter the verification code sent to your Telegram
3. If you have 2FA enabled, enter your password
4. Select the groups you want to KEEP (uncheck the ones to leave)
5. Click "Start Cleanup" to begin the process
6. Wait for the cleanup to complete - your session will be logged out automatically

## Security Notes

- Your API credentials are stored securely in environment variables
- Sessions are temporary and cleared after cleanup
- No user data is stored permanently
- All operations are performed client-side with your credentials

## Limitations

- Free version allows keeping max 10 groups per cleanup
- Pro version removes this limitation (contact developer)

## Support

For issues or feature requests, please contact the developer.

## License

This project is for educational purposes. Use responsibly and in accordance with Telegram's Terms of Service.