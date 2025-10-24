from time import sleep
import pika

# Connexion à RabbitMQ (localhost:5672, avec identifiants)
try:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='192.168.1.56',
            port=5672,
            credentials=pika.PlainCredentials('user', 'password')
        )
    )
except pika.exceptions.AMQPConnectionError as e:
    print(f"Erreur de connexion à RabbitMQ: {e}")
    exit(1)
channel = connection.channel()

# On s'assure que la file "hello" existe
channel.queue_declare(queue='hello')

iterator = 0
while True:
    # Envoi d'un message
    channel.basic_publish(
        exchange='',
        routing_key='hello',  # le nom de la file
        body='Hello RabbitMQ! Message numéro {}'.format(iterator)
    )

    print(" [x] Message envoyé: 'Hello RabbitMQ!'")
    iterator += 1
    sleep(1)  # Attendre 5 secondes avant d'envoyer le prochain message

connection.close()
