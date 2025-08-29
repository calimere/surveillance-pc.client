import requests

DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1385605345992380466/qJkZq1OVapB8E2NeWTf-ncHUA_nkpxpuK8E1jOjdTk8xGekhBjSoEf-rd6nEv9gyWO5s'

def send_discord_notification(message):
    data = { "content": message }
    requests.post(DISCORD_WEBHOOK_URL, json=data)