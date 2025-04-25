import asyncio
from telethon import TelegramClient, events
from quotexapi.stable_api import Quotex
import re
from datetime import datetime, timedelta
import pytz
import os
import time

# Telegram API credentials
api_id = 23844616
api_hash = '4aeca3680a20f9b8bc669f9897d5402f'
phone = '+919761085591'
main_channel_id = -1002178379771  # Main channel ID
other_channel_id = -1002695493762  # Target channel ID

# Initialize the Telegram client
client = TelegramClient('session_name', api_id, api_hash)

async def main():
    # Hardcoded Quotex credentials
    email = "mashupcartoon@gmail.com"
    password = "Aayat@8055"

    # Initialize Quotex client
    quotex_client = Quotex(email=email, password=password)

    # Connect to Quotex
    connect_status, reason = await quotex_client.connect()
    if not connect_status:
        print(f"Failed to connect to Quotex: {reason}")
        return

    # Set to practice mode (optional, kept for consistency)
    quotex_client.set_account_mode("PRACTICE")

    def parse_signal(message):
        """Parse the incoming trading signal message into a dictionary."""
        lines = message.split('\n')
        signal = {}
        for line in lines:
            line = line.strip()
            if line.startswith('💷'):
                signal['currency_pair'] = line[2:].strip()
            elif line.startswith('⏰'):
                signal['time'] = line[2:].strip()
            elif line.startswith('🔴') or line.startswith('🟢'):
                action = line[2:].strip().replace('⤵️', '').replace('⤴️', '').strip()
                signal['action'] = action
        return signal

    @client.on(events.NewMessage(chats=main_channel_id))
    async def handler(event):
        """Handle new messages, send signal as caption with image, and check result using candles."""
        signal = parse_signal(event.message.message)
        required_keys = ['currency_pair', 'time', 'action']
        if all(key in signal for key in required_keys):
            # Map the action to the new format
            action_map = {
                "Put DOWN": "DOWN 🟥",
                "Call UP": "UP 🟩"
            }
            mapped_action = action_map.get(signal['action'], signal['action'])
            
            # Replace timezone indicator
            time_str = signal['time'].replace('[🇹🇷]', '[ UTC +03:00 ]')
            
            # Construct the formatted signal message with bold text
            formatted_message = f"""
📊 **{signal['currency_pair']}**
⏰ **{time_str}**
⏳ **M1 [1-Minute]**
↕️ **{mapped_action}**
💬 **@ZoyaAckerman**
"""
            # Path to the image in the same directory
            image_path = "ZOYA.jpg"
            
            # Send the image with the formatted message as caption
            await client.send_file(
                other_channel_id,
                image_path,
                caption=formatted_message,
                parse_mode='markdown'
            )
            
            # Prepare for result checking
            currency_pair = signal['currency_pair']
            action = signal['action']
            time_str = signal['time']
            
            # Handle OTC pairs for API by replacing '-OTC' with '_otc'
            asset = currency_pair.replace('-OTC', '_otc')
            
            # Parse trade time
            match = re.search(r'(\d{2}):(\d{2})', time_str)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                tz = pytz.timezone('Etc/GMT-3')  # UTC +03:00
                now_local = datetime.now(tz)
                trade_time_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
                trade_time_utc = trade_time_local.astimezone(pytz.utc)
                
                # Wait until 2 minutes and 5 seconds after the signal time
                # This ensures both candles have completed
                check_time_utc = trade_time_utc + timedelta(minutes=2, seconds=5)
                now_utc = datetime.now(pytz.utc)
                
                if check_time_utc < now_utc:
                    print(f"Check time {check_time_utc} is in the past, skipping.")
                    return
                
                # Calculate sleep time
                sleep_seconds = (check_time_utc - now_utc).total_seconds()
                print(f"Signal time: {trade_time_utc}")
                print(f"Waiting {sleep_seconds} seconds until both candles are completed")
                await asyncio.sleep(sleep_seconds)
                
                # After waiting, fetch both candles at once
                try:
                    # Fetch candles (this will include both the first and second candles)
                    candles = await quotex_client.get_candles(asset, int(time.time()), 200, 60)
                    print(f"Fetched {len(candles)} candles for {asset}")
                    
                    # Calculate the timestamps for the first and second candles
                    first_candle_timestamp = int(trade_time_utc.timestamp())
                    second_candle_timestamp = first_candle_timestamp + 60  # Add 60 seconds for the next candle
                    
                    # Find the first and second candles by their timestamps
                    first_candle = next((c for c in candles if c['time'] == first_candle_timestamp), None)
                    second_candle = next((c for c in candles if c['time'] == second_candle_timestamp), None)
                    
                    # Log the candle information
                    if first_candle:
                        first_open = first_candle['open']
                        first_close = first_candle['close']
                        first_color = "Green" if first_close > first_open else "Red"
                        print(f"First Candle: Time: {datetime.fromtimestamp(first_candle_timestamp)}, Open: {first_open}, Close: {first_close}, Color: {first_color}")
                    else:
                        print(f"First candle not found for timestamp {first_candle_timestamp}")
                    
                    if second_candle:
                        second_open = second_candle['open']
                        second_close = second_candle['close']
                        second_color = "Green" if second_close > second_open else "Red"
                        print(f"Second Candle: Time: {datetime.fromtimestamp(second_candle_timestamp)}, Open: {second_open}, Close: {second_close}, Color: {second_color}")
                    else:
                        print(f"Second candle not found for timestamp {second_candle_timestamp}")
                    
                    # Determine the result based on both candles
                    expected_color = "Green" if "Call" in action else "Red"
                    direction_text = "Up 🟩" if "Call" in action else "Down 🟥"
                    result_message = ""
                    is_win = False  # Flag to track if this was a win (either direct or MTG)
                    
                    # Check first candle for direct win
                    if first_candle and first_color == expected_color:
                        result_message = (
                            f"**🏁 Result Of Trade :**\n"
                            f"**📊 {currency_pair}**\n"
                            f"**↕️ {direction_text}**\n"
                            f"**🌐 WIN ☑️**\n"
                            f"**🃏 $4.50**"
                        )
                        is_win = True
                    # Check second candle for MTG win
                    elif second_candle and second_color == expected_color:
                        result_message = (
                            f"**🏁 Result Of Trade :**\n"
                            f"**📊 {currency_pair}**\n"
                            f"**↕️ {direction_text}**\n"
                            f"**🌐 MTG WIN ☑️**\n"
                            f"**🃏 $3.50**"
                        )
                        is_win = True
                    # Neither candle matched - it's a loss
                    else:
                        result_message = (
                            f"**🏁 Result Of Trade :**\n"
                            f"**📊 {currency_pair}**\n"
                            f"**↕️ {direction_text}**\n"
                            f"**🌐 LOSS ⚒️**\n"
                            f"**🃏 $-5.00**"
                        )
                    
                    # Send the result message
                    await client.send_message(other_channel_id, result_message, parse_mode='markdown')
                    print(f"Result message sent: {result_message}")
                    
                    # Send additional messages based on result
                    
                    # 1st message - only if it was a WIN (direct or MTG)
                    if is_win:
                        vip_message = "**🦾 JOIN VIP + BOT TO AUTOMATE 90% ACCURATE SIGNALS❕**"
                        await client.send_message(other_channel_id, vip_message)
                        print(f"VIP message sent: {vip_message}")
                    
                    # 2nd message - always sent regardless of result
                    await asyncio.sleep(1)  # Small delay between messages
                    divider_message = "➖➖➖➖➖➖➖➖"
                    await client.send_message(other_channel_id, divider_message)
                    print(f"Divider message sent: {divider_message}")
                    
                except Exception as e:
                    print(f"Error checking candles: {e}")
            else:
                print("Failed to parse time")

    # Start the Telegram client
    await client.start(phone)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())