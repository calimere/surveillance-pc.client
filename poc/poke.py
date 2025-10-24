from asyncio import sleep
import psutil
import requests

alreadySent = False
while(True):
    paintOn = False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == 'mspaint.exe':
                paintOn = True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if paintOn :
        if not alreadySent:
            webhook_url = 'https://discord.com/api/webhooks/1385605345992380466/qJkZq1OVapB8E2NeWTf-ncHUA_nkpxpuK8E1jOjdTk8xGekhBjSoEf-rd6nEv9gyWO5s'
            data = {
                "content": f"Process mspaint.exe starting"
            }
            requests.post(webhook_url, json=data)
            alreadySent = True
    else:
        if alreadySent:
            webhook_url = 'https://discord.com/api/webhooks/1385605345992380466/qJkZq1OVapB8E2NeWTf-ncHUA_nkpxpuK8E1jOjdTk8xGekhBjSoEf-rd6nEv9gyWO5s'
            data = {
                "content": "Process mspaint.exe has stopped running."
            }
            requests.post(webhook_url, json=data)
            alreadySent = False
    
    paintOn = False
    sleep(5)