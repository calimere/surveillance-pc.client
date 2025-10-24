import pika

# Connexion à RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='192.168.1.56',
        port=5672,
        credentials=pika.PlainCredentials('user', 'password')
    )
)
channel = connection.channel()

# On s'assure que la file "hello" existe
channel.queue_declare(queue='hello')

# Callback appelé quand un message arrive
def callback(ch, method, properties, body):
    print(f" [x] Message reçu: {body.decode()}")

# Abonnement à la file "hello"
channel.basic_consume(
    queue='hello',
    on_message_callback=callback,
    auto_ack=True
)

print(" [*] En attente de messages. Ctrl+C pour quitter")
channel.start_consuming()
