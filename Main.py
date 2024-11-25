import json
import os
import curses
import logging
from typing import Dict, List
from CH340 import RelayController, RelayState

CH340 = RelayController()


class Historique:
    def __init__(self, fichier_log: str = "historique_poele.log"):
        self.fichier_log = fichier_log
        # Configuration du logger
        self.logger = logging.getLogger('PoeleLogger')
        self.logger.setLevel(logging.INFO)

        # Gestionnaire de fichier
        handler = logging.FileHandler(fichier_log, encoding='utf-8')
        handler.setLevel(logging.INFO)

        # Format du log
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    def ajouter_evenement(self, type_event: str, details: str):
        """Ajoute un événement dans l'historique"""
        self.logger.info(f"{type_event}: {details}")

    def obtenir_historique(self, nb_lignes: int = 10) -> List[str]:
        """Récupère les dernières lignes de l'historique"""
        if not os.path.exists(self.fichier_log):
            return []

        with open(self.fichier_log, 'r', encoding='utf-8') as f:
            lignes = f.readlines()
            return lignes[-nb_lignes:]


class ConfigurationPoele:
    def __init__(self, fichier_config: str = "config_poele.json"):
        self.fichier_config = fichier_config
        self.historique = Historique()
        self.config_defaut = {
            'temperature_cible': 22.0,
            'vitesse_moteur_max': 2000.0,
            'seuil_temperature_fumee': 200.0,
            'etat': False  # Ajout de l'état du poêle
        }
        self.parametres = self.charger_configuration()

    def charger_configuration(self) -> dict:
        """Charge la configuration depuis le fichier JSON ou crée une configuration par défaut"""
        try:
            if os.path.exists(self.fichier_config):
                with open(self.fichier_config, 'r') as f:
                    config = json.load(f)
                # Vérifie que tous les paramètres requis sont présents
                for key in self.config_defaut:
                    if key not in config:
                        config[key] = self.config_defaut[key]
                self.historique.ajouter_evenement("Configuration", "Configuration chargée avec succès")
                return config
        except Exception as e:
            self.historique.ajouter_evenement("Erreur", f"Erreur de chargement de la configuration: {e}")

        # Si le fichier n'existe pas ou est invalide, utilise la configuration par défaut
        self.sauvegarder_configuration(self.config_defaut)
        return self.config_defaut.copy()

    def sauvegarder_configuration(self, config: dict) -> bool:
        """Sauvegarde la configuration dans le fichier JSON"""
        try:
            with open(self.fichier_config, 'w') as f:
                json.dump(config, f, indent=4)
            self.historique.ajouter_evenement("Configuration", "Configuration sauvegardée")
            return True
        except Exception as e:
            self.historique.ajouter_evenement("Erreur", f"Erreur de sauvegarde: {e}")
            return False

    def modifier_parametre(self, param: str, valeur: float) -> bool:
        """Modifie un paramètre et sauvegarde la configuration"""
        if param in self.parametres:
            ancienne_valeur = self.parametres[param]
            self.parametres[param] = valeur
            if self.sauvegarder_configuration(self.parametres):
                self.historique.ajouter_evenement(
                    "Modification paramètre",
                    f"{param}: {ancienne_valeur} → {valeur}"
                )
                return True
        return False

    def modifier_etat(self, nouvel_etat: bool) -> bool:
        """Modifie l'état du poêle et sauvegarde la configuration"""
        ancien_etat = self.parametres.get('etat', False)
        self.parametres['etat'] = nouvel_etat
        if self.sauvegarder_configuration(self.parametres):
            self.historique.ajouter_evenement(
                "Changement état",
                f"{'Arrêt' if ancien_etat else 'Démarrage'} → {'Marche' if nouvel_etat else 'Arrêt'}"
            )
            return True
        return False


class Capteur:
    def __init__(self, nom: str, valeur_initiale: float):
        self.nom = nom
        self.valeur = valeur_initiale

    def lire_valeur(self) -> float:
        """Retourne la valeur actuelle du capteur."""
        return self.valeur

    def mettre_a_jour(self, nouvelle_valeur: float):
        """Met à jour la valeur du capteur."""
        self.valeur = nouvelle_valeur


class ControlePoele:
    def __init__(self):
        self.config = ConfigurationPoele()
        self.parametres = self.config.parametres
        self.en_marche = self.parametres.get('etat', False)
        self.capteurs: Dict[str, Capteur] = {
            'Moteur fumée': Capteur('Moteur fumée', True),
            'Vitesse moteur fumée': Capteur('Vitesse moteur fumée', 1500.0),
            'Moteur ventilation': Capteur('Moteur ventilation', True),
            'Moteur pellet': Capteur('Moteur pellet', True),
            'Température externe': Capteur('Température Externe', 20.0),
            'Humidite externe': Capteur('Humidité', 45.0),
            'Température fumée': Capteur('Température Fumée', 150.0),
            'Presosta': Capteur('Presosta', 10),
            'Etat_coupe_circuit': Capteur('Etat_coupe_circuit', False),
        }

    # Relay 1 = Moteur fumée
    # Relay 2 = Moteur ventilation
    # Relay 3 = Moteur vis pellet
    # Relay 4 = Résistance chauffante
    # Relay 7 = Coupe circuit -> retour ON / OFF
    # Relay 8 = Presosta -> retour ON / OFF
    # Pin 1 = Capteur Temp / hum -> VCC 3.3V
    # Pin 6 = Capteur Temp / hum -> GND
    # Pin 7 = Capteur Temp / hum -> GPIO / SIG
    # Pin 13 = Sonde de température +600C° -> GPIO
    # Pin 14 = Sonde de température +600C° -> GND
    # Pin 17 = Sonde de température +600C° -> 3.3V
    # Pin 30 = PWM Moteur fumée -> GND
    # Pin 32 = PWM Moteur fumée -> GPIO

    def obtenir_valeurs_capteurs(self):
        """Retourne les valeurs actuelles des capteurs sous forme de dictionnaire."""
        return {nom: capteur.lire_valeur() for nom, capteur in self.capteurs.items()}

    def demarrer(self):
        self.en_marche = True
        self.config.modifier_etat(True)
        CH340.toggle_relay(1)
        return "Démarrage du poêle..."

    def arreter(self):
        self.en_marche = False
        self.config.modifier_etat(False)
        CH340.toggle_relay(1)
        return "Arrêt du poêle..."

    def modifier_parametre(self, param: str, valeur: float) -> str:
        if param in self.parametres:
            if self.config.modifier_parametre(param, valeur):
                self.parametres = self.config.parametres
                return f"Paramètre {param} modifié à {valeur}"
            return "Erreur lors de la sauvegarde du paramètre"
        return "Paramètre invalide"


class Interface:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.poele = ControlePoele()
        self.menu_principal = [
            "Démarrer/Arrêter le poêle",
            "Afficher les capteurs",
            "Modifier les paramètres",
            "Voir l'historique",
            "Quitter"
        ]
        self.menu_parametres = [
            "Température cible",
            "Vitesse moteur maximale",
            "Seuil température fumée",
            "Retour au menu principal"
        ]
        self.menu_capteurs = [
            "Température Externe",
            "Humidité",
            "Température Fumée",
            "Vitesse Moteur",
            "Retour au menu principal"
        ]
        self.position = 0
        self.position_principale = 0  # Nouvelle variable pour stocker la position du menu principal
        self.message = ""
        curses.curs_set(0)  # Cache le curseur
        curses.start_color()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Pour la sélection
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Pour les messages
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Pour les valeurs
        self.stdscr.timeout(1000)  # Rafraîchissement toutes les secondes

    def afficher_menu(self, menu: List[str], titre: str):
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()

        # Affiche le titre
        self.stdscr.addstr(1, 2, f"=== {titre} ===")

        # Affiche l'état du poêle
        etat = "En marche" if self.poele.en_marche else "Arrêté"
        self.stdscr.addstr(3, 2, f"État du poêle: {etat}")

        # Affiche le message
        if self.message:
            self.stdscr.addstr(height - 2, 2, self.message, curses.color_pair(2))

        # Affiche le menu
        for idx, item in enumerate(menu):
            y = 5 + idx
            # Utilise position_principale pour le menu principal, sinon utilise position
            current_pos = self.position_principale if menu == self.menu_principal else self.position
            if idx == current_pos:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, 2, f"> {item}")
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(y, 2, f"  {item}")

        self.stdscr.refresh()

    def afficher_historique(self):
        """Affiche l'historique des modifications et des états"""
        self.position = 0
        historique = self.poele.config.historique.obtenir_historique()

        while True:
            self.stdscr.clear()
            self.stdscr.addstr(1, 2, "=== Historique du Poêle ===")

            # Affichage des entrées de l'historique
            ligne_debut = max(0, self.position)
            for idx, ligne in enumerate(historique[ligne_debut:ligne_debut + 10]):
                y = 3 + idx
                self.stdscr.addstr(y, 2, ligne.strip())

            # Instructions
            self.stdscr.addstr(14, 2, "↑/↓: Naviguer  |  q: Retour au menu principal")
            self.stdscr.refresh()

            # Gestion des touches
            key = self.stdscr.getch()
            if key == ord('q'):
                self.position = 0  # Réinitialise la position locale
                break
            elif key == curses.KEY_UP and self.position > 0:
                self.position -= 1
            elif key == curses.KEY_DOWN and self.position < len(historique) - 10:
                self.position += 1

    def menu_principal_action(self):
        if self.position_principale == 0:
            self.message = self.poele.demarrer() if not self.poele.en_marche else self.poele.arreter()
        elif self.position_principale == 1:
            self.afficher_capteurs()
        elif self.position_principale == 2:
            self.gerer_parametres()
        elif self.position_principale == 3:
            self.afficher_historique()
        elif self.position_principale == 4:
            return False
        return True

    def gerer_parametres(self):
        self.position = 0
        while True:
            self.afficher_menu(self.menu_parametres, "Réglage des Paramètres")
            key = self.stdscr.getch()

            if key == curses.KEY_UP and self.position > 0:
                self.position -= 1
            elif key == curses.KEY_DOWN and self.position < len(self.menu_parametres) - 1:
                self.position += 1
            elif key == 10:  # Touche Entrée
                if self.position == len(self.menu_parametres) - 1:
                    self.position = 0  # Réinitialise la position locale
                    break
                else:
                    self.modifier_parametre(self.position)

    def executer(self):
        while True:
            self.afficher_menu(self.menu_principal, "Menu Principal")
            key = self.stdscr.getch()

            if key == curses.KEY_UP and self.position_principale > 0:  # Utilise position_principale
                self.position_principale -= 1
            elif key == curses.KEY_DOWN and self.position_principale < len(self.menu_principal) - 1:
                self.position_principale += 1
            elif key == 10:  # Touche Entrée
                if not self.menu_principal_action():
                    break

    def afficher_capteurs(self):
        """Affiche les valeurs des capteurs"""
        self.position = 0
        while True:
            self.stdscr.clear()
            self.stdscr.addstr(1, 2, "=== État des Capteurs ===")

            # Affiche les valeurs des capteurs
            valeurs = self.poele.obtenir_valeurs_capteurs()
            for idx, (capteur, valeur) in enumerate(valeurs.items()):
                y = 3 + idx
                if idx == self.position:
                    self.stdscr.attron(curses.color_pair(1))
                    self.stdscr.addstr(y, 2, f"> {capteur}: {valeur}")
                    self.stdscr.attroff(curses.color_pair(1))
                else:
                    self.stdscr.addstr(y, 2, f"  {capteur}: {valeur}")

            # Option retour
            retour_y = 3 + len(valeurs)
            if self.position == len(valeurs):
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(retour_y, 2, "> Retour au menu principal")
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(retour_y, 2, "  Retour au menu principal")

            # Instructions
            self.stdscr.addstr(retour_y + 2, 2, "Utilisez ↑/↓ pour naviguer, Entrée pour sélectionner")
            self.stdscr.refresh()

            # Gestion des touches
            key = self.stdscr.getch()
            if key == curses.KEY_UP and self.position > 0:
                self.position -= 1
            elif key == curses.KEY_DOWN and self.position < len(valeurs):
                self.position += 1
            elif key == 10:  # Touche Entrée
                if self.position == len(valeurs):  # Option "Retour"
                    self.position = 0  # Réinitialise la position locale
                    break

    def modifier_parametre(self, param_idx: int):
        # Gère la modification d'un paramètre spécifique
        params = ['temperature_cible', 'vitesse_moteur_max', 'seuil_temperature_fumee']
        if param_idx >= len(params):
            return

        param = params[param_idx]
        valeur_precedente = self.poele.parametres[param]

        while True:
            self.stdscr.clear()
            self.stdscr.addstr(1, 2, f"=== Modification de {param} ===")
            self.stdscr.addstr(3, 2, f"Valeur actuelle: {valeur_precedente}")
            self.stdscr.addstr(5, 2, "Nouvelle valeur: ")
            self.stdscr.addstr(7, 2, "Appuyez sur Entrée pour confirmer ou Echap pour annuler")

            if self.message:
                self.stdscr.addstr(9, 2, self.message, curses.color_pair(2))

            # Désactive l'écho automatique des caractères
            curses.noecho()
            curses.curs_set(1)  # Affiche le curseur

            # Position du curseur pour la saisie
            self.stdscr.move(5, 18)
            self.stdscr.refresh()

            # Récupération de la saisie caractère par caractère
            saisie = ""
            pos_x = 18  # Position initiale du curseur

            while True:
                try:
                    char = self.stdscr.getch()

                    # Touche Echap
                    if char == 27:
                        curses.curs_set(0)  # Cache le curseur
                        self.message = "Modification annulée"
                        return

                    # Touche Entrée
                    elif char == 10:
                        break

                    # Touche Retour arrière
                    elif char == curses.KEY_BACKSPACE or char == 127 or char == 8:
                        if saisie:
                            saisie = saisie[:-1]
                            pos_x -= 1
                            self.stdscr.addstr(5, 18, " " * 20)  # Efface la ligne
                            self.stdscr.addstr(5, 18, saisie)
                            self.stdscr.move(5, pos_x)

                    # Caractères normaux (chiffres et point décimal)
                    elif (char in [ord(str(i)) for i in range(10)] or char == ord('.')) and len(saisie) < 20:
                        saisie += chr(char)
                        self.stdscr.addch(5, pos_x, chr(char))
                        pos_x += 1

                    self.stdscr.refresh()

                except curses.error:
                    pass

            curses.curs_set(0)  # Cache le curseur

            # Validation de la saisie
            if not saisie:
                self.message = "Erreur: Aucune valeur saisie"
                continue

            try:
                nouvelle_valeur = float(saisie)

                # Validation des plages de valeurs selon le paramètre
                if param == 'temperature_cible':
                    if nouvelle_valeur < 15 or nouvelle_valeur > 30:
                        self.message = "Erreur: La température doit être entre 10°C et 30°C"
                        continue
                elif param == 'vitesse_moteur_max':
                    if nouvelle_valeur < 1000 or nouvelle_valeur > 2000:
                        self.message = "Erreur: La vitesse doit être entre 500 et 3000 tr/min"
                        continue
                elif param == 'seuil_temperature_fumee':
                    if nouvelle_valeur < 100 or nouvelle_valeur > 300:
                        self.message = "Erreur: Le seuil doit être entre 100°C et 300°C"
                        continue

                self.poele.modifier_parametre(param, nouvelle_valeur)
                self.message = f"Paramètre {param} modifié: {valeur_precedente} → {nouvelle_valeur}"
                break

            except ValueError:
                self.message = "Erreur: Veuillez entrer un nombre valide"
                continue


def main():
    curses.wrapper(lambda stdscr: Interface(stdscr).executer())


if __name__ == "__main__":
    main()
    CH340.cleanup()
