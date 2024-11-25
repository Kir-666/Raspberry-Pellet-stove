import threading
import serial
import serial.tools.list_ports
import time
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


def find_ch340_port() -> Optional[str]:
    """
    Cherche et retourne le port du CH340 spécifiquement pour le VID:PID 1a86:7523
    """
    ports = serial.tools.list_ports.comports()

    print("Recherche du CH340...")
    print("Ports disponibles :")

    for port in ports:
        print(f"\nExamen du port: {port.device}")
        print(f"Description: {port.description}")
        print(f"Hardware ID: {port.hwid}")
        print(f"VID:PID: {port.vid:04x}:{port.pid:04x}")

        # Vérifie spécifiquement le VID:PID de votre CH340
        if port.vid == 0x1a86 and port.pid == 0x7523:
            print(f"\nCH340 trouvé sur le port: {port.device}")
            print("Vérification des permissions...")

            # Vérifie les permissions du port
            import os
            try:
                # Essaie d'ouvrir le port en lecture/écriture
                with serial.Serial(port.device) as ser:
                    print("Test de connexion réussi!")
                return port.device
            except PermissionError:
                print(f"Erreur de permission sur {port.device}")
                print("Exécutez: sudo usermod -a -G dialout $USER")
                print("Puis redémarrez le Raspberry Pi")
                raise Exception("Erreur de permission sur le port série")
            except Exception as e:
                print(f"Erreur lors du test du port: {e}")
                raise

    print("\nAucun CH340 (1a86:7523) trouvé!")
    return None


class RelayState(Enum):
    OFF = 0
    ON = 1

    def __str__(self):
        return 'On' if self == RelayState.ON else 'Off'


@dataclass
class RelayCommand:
    ON: bytes
    OFF: bytes
    STATUS: bytes


class RelayController:
    def __init__(self, port: Optional[str] = None, baudrate: int = 9600, num_relays: int = 8):
        # Si aucun port n'est spécifié, cherche automatiquement le CH340
        if port is None:
            port = find_ch340_port()
            if port is None:
                raise Exception("Aucun CH340 trouvé. Vérifiez la connexion USB.")

        try:
            self.serial_port = serial.Serial(port, baudrate)
            print(f"Connexion établie sur {port}")
        except serial.SerialException as e:
            print(f"Erreur lors de la connexion au port {port}: {e}")
            raise

        self.num_relays = num_relays
        self.states = [RelayState.OFF] * num_relays
        self.running = True

        # Définition des commandes
        self.commands = [
            RelayCommand(
                ON=f'AT+O{i + 1}'.encode(),
                OFF=f'AT+C{i + 1}'.encode(),
                STATUS=f'AT+R{i + 1}'.encode()
            ) for i in range(num_relays)
        ]
        self.all_on_cmd = b'AT+AO'
        self.all_off_cmd = b'AT+AC'

        # Démarrage du thread de lecture
        self.reader_thread = threading.Thread(target=self._read_from_port, daemon=True)
        self.reader_thread.start()

    def _read_from_port(self):
        """Lit en continu les messages du port série."""
        while self.running:
            try:
                if self.serial_port.in_waiting:
                    chars = self.serial_port.readline()
                    self._process_message(chars)
            except serial.SerialException as e:
                print(f'Erreur de port série: {e}')
                self.running = False
            except Exception as e:
                print(f'Erreur de lecture: {e}')
            time.sleep(0.1)  # Évite une utilisation CPU excessive

    def _process_message(self, chars):
        """Traite les messages entrants du module relais."""
        try:
            parts = chars.split()
            if len(parts) == 2:
                channel_map = {f'CH{i}:'.encode(): i for i in range(1, self.num_relays + 1)}
                state_map = {b'OFF': RelayState.OFF, b'ON': RelayState.ON}

                channel = channel_map.get(parts[0])
                state = state_map.get(parts[1])

                if channel is not None and state is not None:
                    print(f'Relais {channel} = {state}')
                    self.states[channel - 1] = state
            elif chars:
                print(f'Message relais: {chars}')
        except Exception as e:
            print(f'Erreur de traitement du message: {e}')

    def toggle_relay(self, relay_num: int):
        """Change l'état d'un relais spécifique."""
        if 1 <= relay_num <= self.num_relays:
            idx = relay_num - 1
            new_state = RelayState.OFF if self.states[idx] == RelayState.ON else RelayState.ON
            cmd = self.commands[idx].OFF if new_state == RelayState.OFF else self.commands[idx].ON

            try:
                self.serial_port.write(cmd)
                self.states[idx] = new_state
                print(f'Relais {relay_num} mis à {new_state}')
            except serial.SerialException as e:
                print(f'Erreur lors du changement du relais {relay_num}: {e}')

    def set_all_relays(self, state: RelayState):
        """Change l'état de tous les relais."""
        try:
            cmd = self.all_on_cmd if state == RelayState.ON else self.all_off_cmd
            self.serial_port.write(cmd)
            self.states = [state] * self.num_relays
            print(f'Tous les relais mis à {state}')
        except serial.SerialException as e:
            print(f'Erreur lors du changement de tous les relais: {e}')

    def display_menu(self) -> int:
        """Affiche le menu de contrôle et obtient le choix de l'utilisateur."""
        menu_text = '\nMenu:\n'
        for i in range(self.num_relays):
            menu_text += f' {i + 1} : Relais {i + 1} ({self.states[i]})\n'
        menu_text += ' 9 : Vérification status\n'
        menu_text += '10 : Tout allumer\n'
        menu_text += '11 : Tout éteindre\n'
        menu_text += '12 : Quitter\n'
        menu_text += ' %> '

        try:
            choice = input(menu_text)
            return int(choice) if choice.isdigit() else 0
        except ValueError:
            return 0

    def run(self):
        """Boucle principale de contrôle."""
        print('--------------------------------')
        print('Contrôle de Relais USB CH340')
        print('--------------------------------')

        while self.running:
            choice = self.display_menu()

            if 1 <= choice <= self.num_relays:
                self.toggle_relay(choice)
            elif choice == 10:
                self.set_all_relays(RelayState.ON)
            elif choice == 11:
                self.set_all_relays(RelayState.OFF)
            elif choice == 12:
                self.running = False
            else:
                print(f'Choix invalide: {choice}')

    def cleanup(self):
        """Nettoie les ressources."""
        self.running = False
        if hasattr(self, 'serial_port') and self.serial_port.is_open:
            self.serial_port.close()
        if hasattr(self, 'reader_thread'):
            self.reader_thread.join(timeout=1.0)


if __name__ == '__main__':
    try:
        # Détection automatique du port CH340
        controller = RelayController()  # Sans spécifier de port
        controller.run()
    except Exception as e:
        print(f"Erreur: {e}")
    finally:
        if 'controller' in locals():
            controller.cleanup()