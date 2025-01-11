import random
from diplomacy import Game
from diplomacy.utils.export import to_saved_game_format
from diplomacy.engine.message import Message
from itertools import combinations
from openai import OpenAI
import re

def extract_messages(input_string):
    if input_string == "DONE":
        return {}
    # Extract the content between MESSAGES_START and MESSAGES_END
    match = re.search(r"\$\$MESSAGES_START\$\$(.*?)\$\$MESSAGES_END\$\$", input_string, re.DOTALL)
    if not match:
        print(input_string)
        raise ValueError("Input string does not contain valid message boundaries.")

    messages_content = match.group(1).strip()

    # Parse the individual messages
    messages = re.findall(r"@@(.*?)\*\*(.*?)\*\*@@", messages_content, re.DOTALL)

    # Convert to a dictionary
    messages_dict = {country.strip(): message.strip() for country, message in messages}

    return messages_dict

def extract_orders(input_string):
    if input_string == "DONE":
        return {}
    # Extract the content between MESSAGES_START and MESSAGES_END
    match = re.search(r"\$\$ORDERS_START\$\$(.*?)\$\$ORDERS_END\$\$", input_string, re.DOTALL)
    if not match:
        print(input_string)
        raise ValueError("Input string does not contain valid message boundaries.")

    messages_content = match.group(1).strip()

    # Parse the individual messages
    messages = re.findall(r"@@(.*?)\*\*(.*?)\*\*@@", messages_content, re.DOTALL)

    # Convert to a dictionary
    messages_dict = {country.strip(): message.strip() for country, message in messages}

    return messages_dict

def generate_player_battle_turn_system_prompt(player, power, other_powers, game, rounds_left):
    prompt = []
    prompt.append("\n")
    prompt.append("You are playing as ")
    prompt.append(power + "\n")

    prompt.append("The current state of the game")
    for power_name, power in game.powers.items():
        prompt.append(str(power))
    prompt.append("\nYou are in the movement phase\n")
    prompt.append("The other players in the game are ")
    for opower in other_powers:
        prompt.append(opower + " ")
    prompt.append("\n")
    prompt.append("Here are the orders you can preform in the format\n")
    possible_orders = game.get_all_possible_orders()
    for loc in game.get_orderable_locations(player):
        if possible_orders[loc]:
            for order in possible_orders[loc]:
                prompt.append(order + " ")
    
    prompt.append("By listings the orders you want to send in the format\n")
    prompt.append("$$ORDERS_START$$")
    prompt.append("@@AUSTRIA **A BUD - GAL**@@")
    prompt.append("$$ORDERS_END$$")
    '''
    prompt.append("You can send the same order to all of powers at once\n")
    prompt.append("By listings the order you want to send in the format\n")
    prompt.append("$$ORDER_START$$")
    prompt.append("@@ALL **A BUD - GAL**@@")
    prompt.append("$$ORDER_END$$")
    '''
    prompt.append("Or you can elect to no longer send orders and move too the next negotiation phase\n")
    prompt.append("By saying DONE")
    prompt.append("Just list the order, no need to explain your thinking, or add any form of structure othe then what has been asked for")
    return "".join(prompt)

def generate_player_negotioation_system_prompt(player, power, other_powers, game, inter_player_message, rounds_left):
    prompt = []
    prompt.append("\n")
    prompt.append("You are playing as ")
    prompt.append(power + "\n")

    prompt.append("The current state of the game")
    for power_name, power in game.powers.items():
        prompt.append(str(power))
    prompt.append("\nYou are in the negotiation phase\n")
    prompt.append(inter_player_message)
    prompt.append("You can choose send a message to one of the following powers if you want, you cannot send one to yourself")
    for opower in other_powers:
        prompt.append(opower + " ")
    prompt.append("\n")
    prompt.append("By listings the messages you want to send in the format\n")
    prompt.append("$$MESSAGES_START$$")
    prompt.append("@@AUSTRIA **Hey want to attack FRANCE**@@")
    prompt.append("$$MESSAGES_END$$")
    '''
    prompt.append("You can send the same message to all of powers at once\n")
    prompt.append("By listings the message you want to send in the format\n")
    prompt.append("$$MESSAGE_START$$")
    prompt.append("@@ALL **ITALY BETRAYED ME**@@")
    prompt.append("$$MESSAGE_END$$")
    '''
    prompt.append("Or you can elect to no longer send messages and move too battle phase\n")
    prompt.append("By saying DONE")
    prompt.append("Just list the message, no need to explain your thinking, or add any form of structure othe then what has been asked for")
    prompt.append("You have " + str(rounds_left) + " rounds left to negotiate")
    prompt.append("What do you want to do?")
    return "".join(prompt)

class PowerWrapper:
    def __init__(self, power):
        self.power = power
        self.conversations = {}

    def set_conversation(self, other, conversation):
        self.conversations[other] = conversation

def create_openai_client():
    """
    Creates and returns an OpenAI client instance using an API key stored in 'file.txt'.
    """
    with open("file.txt", "r", encoding="utf-8") as file:
        api_key = file.read().strip()
    openai = OpenAI()
    openai.api_key = api_key
    return openai


class NegotionState:
    def __init__(self, game):
        self.power = []
        self.rounds_left = 5
        for power in game.powers:
            self.power.append(power)

    def remove_player_from_game(self, player):
        self.power.remove(player)
    
    def get_current_powers(self):
        return self.power   
    
class BattleState:
    def __init__(self, game):
        self.game = game
    

class DiploController:
    def __init__(self, powers, players_to_power_map):
        self.power_wrappers = {}
        for power in powers:
            self.power_wrappers[power] = PowerWrapper(power)

        self.client = create_openai_client()
        self.game = Game()
        unique_pairs = list(combinations(powers, 2))
        for a, b in unique_pairs:
            conversation = Conversation([a, b])
            self.power_wrappers[a].set_conversation(b, conversation)
            self.power_wrappers[b].set_conversation(a, conversation)
        for power, name in players_to_power_map.items():
            self.game.set_controlled(power, name)
        self.players_to_power_map = players_to_power_map
        self.powers = powers
        self.negotiation_state = NegotionState(self.game)

    def add_message_to_conversation(self, sender, receiver, message):
        if sender == receiver:
            return
        print(sender, " sent ",receiver , " a message ", message)
        if sender not in self.power_wrappers or receiver not in self.power_wrappers[sender].conversations:
            return
        self.power_wrappers[sender].conversations[receiver].add_message(sender, message)

    def run_negotiation_turn(self):
        if self.negotiation_state.get_current_powers() == []:
            print("Game is over")
            return
        for power, character_name in self.players_to_power_map.items():
            current_powers = self.negotiation_state.get_current_powers()
            # we want to skip this person if they have left the game
            
            if power not in current_powers:
                continue
            
            filtered_list = [s for s in current_powers if s != power]
            player_messages = self.power_wrappers[power]
            inter_player_messages = ""
            for receiver, conversation in player_messages.conversations.items():
                single_message = "Your conversation with " + receiver + " so far is "
                conversation_log = conversation.dump_to_string()
                if conversation_log == None:
                    single_message = "You have yet to talk with " + receiver + "\n"
                else:
                    single_message += conversation_log
                inter_player_messages += single_message
            prompt = generate_player_negotioation_system_prompt(power, character_name, filtered_list, self.game, inter_player_messages, self.negotiation_state.rounds_left)

            completion = self.client.chat.completions.create(
                model="gpt-4o",
                store=True,
                messages=[
                    {"role":"system", "content": "You are a player in a game of Diplomacy"},
                    {"role": "user", "content": prompt}
                ]
            )
            incoming_message = completion.choices[0].message.content
            if incoming_message == "DONE":
                print("Player ", power, " has left the round")
                
                self.negotiation_state.remove_player_from_game(power)
                continue
            
            messages = extract_messages(incoming_message)
            for recipient_name, message in messages.items():
                self.add_message_to_conversation(power, recipient_name, message)
        self.negotiation_state.rounds_left -= 1
    
    def run_battle_turn(self):
        if self.negotiation_state.get_current_powers() == []:
            print("Game is over")
            return
        for power, character_name in self.players_to_power_map.items():
            current_powers = self.negotiation_state.get_current_powers()
            # we want to skip this person if they have left the game
            
            if power not in current_powers:
                continue
            
            filtered_list = [s for s in current_powers if s != power]
            player_messages = self.power_wrappers[power]
            inter_player_messages = ""
            for receiver, conversation in player_messages.conversations.items():
                single_message = "Your conversation with " + receiver + " so far is "
                conversation_log = conversation.dump_to_string()
                if conversation_log == None:
                    single_message = "You have yet to talk with " + receiver + "\n"
                else:
                    single_message += conversation_log
                inter_player_messages += single_message
            prompt = generate_player_battle_turn_system_prompt(power, character_name, filtered_list, self.game, self.negotiation_state.rounds_left)

            completion = self.client.chat.completions.create(
                model="gpt-4o",
                store=True,
                messages=[
                    {"role":"system", "content": "You are a player in a game of Diplomacy"},
                    {"role": "user", "content": prompt}
                ]
            )
            incoming_message = completion.choices[0].message.content
            messages = extract_orders(incoming_message)
            print(messages)
            for recipient_name, order in messages.items():
                self.game.set_orders(power, order)
            #exit()
        self.game.process()
        self.game.render(output_path="output_end.svg")


class Conversation:
    def __init__(self, members):
        self.message_log = []
        self.members = members

    
    def add_message(self, sender, message):
        message_obj = {}
        message_obj["sender"] = sender
        message_obj["content"] = message 
        self.message_log.append(message_obj)

    def dump_to_string(self):
        if len(self.message_log) == 0:
            return None
        else:
            final_message = ""
            for message_obj in self.message_log:
                final_message += "From " + message_obj["sender"] + "\n"
                final_message += message_obj["content"] + "\n"
            return final_message


powers_list = ["TURKEY", "RUSSIA", "ITALY", "GERMANY", "FRANCE", "ENGLAND", "AUSTRIA"]

players_to_power_map = {
    "TURKEY":"Salim",
    "RUSSIA":"Ivan",
    "ITALY":"Gerabaldi",
    "GERMANY":"Otto",
    "FRANCE":"DeGaul",
    "ENGLAND":"Churchill",
    "AUSTRIA":"Franz"
}

    

controller = DiploController(powers_list, players_to_power_map)
controller.game.render(output_path="output_start.svg")
for i in range(0, 5):
    controller.run_negotiation_turn()
controller.game.process()
print(controller.power_wrappers["TURKEY"].conversations["RUSSIA"].dump_to_string())
print("Going to battle phase")
controller.run_battle_turn()
controller.negotiation_state = NegotionState(controller.game)

controller.game.render(output_path="output_battle_1.svg")
for i in range(0, 5):
    controller.run_negotiation_turn()
controller.run_battle_turn()
controller.negotiation_state = NegotionState(controller.game)

controller.game.render(output_path="output_battle_2.svg")
for i in range(0, 5):
    controller.run_negotiation_turn()
controller.run_battle_turn()
controller.negotiation_state = NegotionState(controller.game)
controller.game.render(output_path="output_battle_3.svg")
for i in range(0, 5):
    controller.run_negotiation_turn()
controller.run_battle_turn()
controller.negotiation_state = NegotionState(controller.game)
controller.game.render(output_path="output_battle_4.svg")
exit()





powers = []





exit()

while not game.is_game_done:

    possible_orders = game.get_all_possible_orders()

    for power_name, power in game.powers.items():
        for loc in game.get_orderable_locations(power_name):
            if possible_orders[loc]:
                for order in possible_orders[loc]:
                    print(order)
        #power_orders = [random.choice(possible_orders[loc]) for loc in game.get_orderable_locations(power_name)
        #                if possible_orders[loc]]
        exit()
        game.set_orders(power_name, power_orders)
        game.process()

