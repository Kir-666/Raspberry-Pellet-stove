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
    for port in ports:
        # Vérifie spécifiquement le VID:PID de votre CH340
        if port.vid == 0x1a86 and port.pid == 0x7523:
            try:
                # Essaie d'ouvrir le port en lecture/écriture
                with serial.Serial(port.device) as ser:
                    pass
                return port.device
            except Exception as e:
                raise PermissionError(f"Erreur d'accès au port  {port.device}: {e}")
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

        self.serial_port = serial.Serial(port, baudrate)
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
            except Exception:
                pass
            time.sleep(0.1)  # Évite une utilisation CPU excessive

    def _process_message(self, chars):
        """Traite les messages entrants du module relais."""
        parts = chars.split()
        if len(parts) == 2:
            channel_map = {f'CH{i}:'.encode(): i for i in range(1, self.num_relays + 1)}
            state_map = {b'OFF': RelayState.OFF, b'ON': RelayState.ON}
            channel = channel_map.get(parts[0])
            state = state_map.get(parts[1])
            if channel is not None and state is not None:
                self.states[channel - 1] = state

    def toggle_relay(self, relay_num: int):
        """Change l'état d'un relais spécifique."""
        if 1 <= relay_num <= self.num_relays:
            idx = relay_num - 1
            new_state = RelayState.OFF if self.states[idx] == RelayState.ON else RelayState.ON
            cmd = self.commands[idx].OFF if new_state == RelayState.OFF else self.commands[idx].ON
            self.serial_port.write(cmd)
            self.states[idx] = new_state

    def set_all_relays(self, state: RelayState):
        """Change l'état de tous les relais."""
        cmd = self.all_on_cmd if state == RelayState.ON else self.all_off_cmd
        self.serial_port.write(cmd)
        self.states = [state] * self.num_relays

    def cleanup(self):
        """Nettoie les ressources."""
        self.running = False
        if hasattr(self, 'serial_port') and self.serial_port.is_open:
            self.serial_port.close()
        if hasattr(self, 'reader_thread'):
            self.reader_thread.join(timeout=1.0)

# Exemple d'utilisation (à exécuter dans un autre script) :
# from CH340 import RelayController, RelayState
# CH340 = RelayController()
# CH340.toggle_relay(1)  # Change l'état du relais 1
# CH340.set_all_relays(RelayState.ON)  # Allume tous les relais
# states_CH340 = CH340.get_relay_states()  # Récupère les états des relais
# CH340.cleanup()  # Libère les ressources
