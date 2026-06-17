import json
from channels.generic.websocket import AsyncWebsocketConsumer

class PriceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join the global price updates group
        self.group_name = 'live_prices'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

        # Send initial success message
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'You are now connected to live price updates!'
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive message from room group
    async def stock_update(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps(message))
