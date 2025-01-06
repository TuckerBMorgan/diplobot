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

def generate_player_system_prompt(player, power, other_powers, game, inter_player_message):
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
    prompt.append("Or you can elect to no longer send messages and move too move phase\n")
    prompt.append("By saying DONE")
    prompt.append("Just list the message, no need to explain your thinking, or add any form of structure othe then what has been asked for")
    prompt.append("What do you want to do?")
    return "".join(prompt)

class PowerWrapper:
    def __init__(self, power):
        self.power = power
        self.conversations = {}

    def set_conversation(self, other, conversation):
        self.conversations[other] = conversation

class DiploController:
    def __init__(self, powers, players_to_power_map):
        self.power_wrappers = {}
        for power in powers:
            self.power_wrappers[power] = PowerWrapper(power)

        self.client = OpenAI()
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

    def add_message_to_conversation(self, sender, receiver, message):
        if sender == receiver:
            return
        print(sender, " sent ",receiver , " a message ", message)
        self.power_wrappers[sender].conversations[receiver].add_message(sender, message)

    def run_negotiation_turn(self):

        for power, character_name in self.players_to_power_map.items():
            filtered_list = [s for s in self.powers if s != power]
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
            prompt = generate_player_system_prompt(power, character_name, filtered_list, self.game, inter_player_messages)

            completion = self.client.chat.completions.create(
                model="gpt-4o",
                store=True,
                messages=[
                    {"role":"system", "content": "You are a player in a game of Diplomacy"},
                    {"role": "user", "content": prompt}
                ]
            )
            messages = extract_messages(completion.choices[0].message.content)
            for recipient_name, message in messages.items():
                self.add_message_to_conversation(power, recipient_name, message)

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
for i in range(0, 5):
    controller.run_negotiation_turn()
print(controller.power_wrappers["TURKEY"].conversations["RUSSIA"].dump_to_string())
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

