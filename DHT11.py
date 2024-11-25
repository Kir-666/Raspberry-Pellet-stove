import RPi.GPIO as GPIO
import time

# Configuration du capteur
DHT_PIN = 4  # Broche GPIO où le capteur DHT11 est connecté

def read_dht11():
    # Lecture des donnée du capteur DHT11
    data = []
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(DHT_PIN, GPIO.OUT)

    # Envoi du signal de démarrage
    GPIO.output(DHT_PIN, GPIO.LOW)
    time.sleep(0.02)  # Maintenir LOW pendant au moins 18ms
    GPIO.output(DHT_PIN, GPIO.HIGH)
    GPIO.setup(DHT_PIN, GPIO.IN)

    # Lecture des impulsions envoyées par le capteur
    for _ in range(500):
        data.append(GPIO.input(DHT_PIN))

    # Analyse des données
    bits = []
    count = 0
    for i in range(len(data)):
        count += 1
        if data[i] == 0:
            if count > 10:  # Filtrer les impulsions longues
                bits.append(1 if count > 20 else 0)
            count = 0

    # Groupes de 8 bits (5 octets : humidité, température, checksum)
    if len(bits) < 40:
        print("Erreur : Données insuffisantes.")
        GPIO.cleanup()
        return None, None

    humidity_bits = bits[0:8]
    temperature_bits = bits[16:24]

    # Conversion des bits en nombres
    humidity = sum([humidity_bits[i] * 2 ** (7 - i) for i in range(8)])
    temperature = sum([temperature_bits[i] * 2 ** (7 - i) for i in range(8)])

    GPIO.cleanup()
    return humidity, temperature


if __name__ == "__main__":
    print("Lecture des données du capteur DHT11...")
    try:
        humidity, temperature = read_dht11()
        if humidity is not None and temperature is not None:
            print(f"Température : {temperature}°C")
            print(f"Humidité : {humidity}%")
        else:
            print("Erreur : Impossible de lire les données du capteur.")
    except KeyboardInterrupt:
        print("\nProgramme interrompu.")
        GPIO.cleanup()
    except Exception as e:
        print(f"Une erreur est survenue : {e}")
        GPIO.cleanup()
