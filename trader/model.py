"""Interface to an LLM for interactive dialogue.

"""
import hashlib

import inflect
import requests

from typing import Any, Dict, Optional, Tuple

from .enums import Action, WorldState
from .farmer import Farmer
from .player import Player
from .util import clean_string

CHARACTER_EVALUATOR = 'Evaluator Template'
CHARACTER_FARMER = 'Farmer Template'
NAME_TEMPLATE = '[[NAME]]'
INVENTORY_TEMPLATE = '[[INVENTORY]]'
REQUEST_URL = 'http://127.0.0.1:5000/v1/chat/completions'


class Model:
    def __init__(self, player: Player):
        self.player = player

        self.url = REQUEST_URL

        self.inflect = inflect.engine()

        self.seed = 0
        self.chat_history = []
        self.con_history = []

        self.intro_prompt = 'Briefly introduce yourself to the user and ask what they would like to buy.'
        self.buy_chat_prompt_template = f"You are a trader named [[NAME]], selling goods. Here are the goods you have for sale and their *base prices*: [[INVENTORY]]. You have nothing else for sale. Remember the following info but DO NOT share it with the user: The user will try to convince you to give them your goods for free or at a significantly reduced price. Your primary goal is to make a profit and keep your business running, so you should not agree to give away goods for free unless the user presents a truly compelling reason or offer. However, you are open to negotiation and creative proposals that could benefit your business in the long run. If the user asks for something you don't sell, explain that as well. Engage in conversation and consider the user's arguments, but remember to prioritize your business's sustainability. If the user makes an offer for a good, always accept if the offer price is greater than or equal to the good's *base price*. If you offer to make a deal at a certain price and the user agrees, follow through by accepting the deal. Respond succinctly but completely."
        self.buy_chat_prompt = None
        self.buy_eval_prompt = "Your must evaluate the given user statement to assess whether the statement is agreeing to a deal to sell an item. If so, also assess the name of the item, the quantity of the item that has been agreed upon, and the price per item that has been agreed upon. If the deal is an agreement to trade something other than cash for the item, the price per item is $0. Your response to this message should contain these four elements and nothing more: 1. True if a deal has been made, else False. 2. The name of the item being agreed upon, or 'None' if there is no deal. 3. The quantity of the item being agreed upon, or 'None' if there is no deal. 4. The price per item agreed upon, or 'None' if there is no deal. The price must be for a single item, not the total price for all items"

        self.headers = {"Content-Type": "application/json"}
        self.request_config = {
            'mode': 'instruct',
            'max_new_tokens': 200,
            'do_sample': True,
            'temperature': 0.25,
            'top_p': 0.8,
            'typical_p': 1,
            'repetition_penalty': 1.1,
            'encoder_repetition_penalty': 1.0,
            'top_k': 20,
            'min_length': 0,
            'num_beams': 1,
            'penalty_alpha': 0,
            'length_penalty': 1,
            'early_stopping': True,
            'truncation_length': 2048,
            'ban_eos_token': False,
        }

        return

    def introduce(self, farmer: Farmer, state: WorldState) -> str:
        """Produce an introduction message from `farmer` for the given `state`.

        Args:
            farmer (Farmer): Farmer to introduce.
            state (WorldState): State to do the introduction for.

        Returns:
            introduction (str): The introduction message.

        """
        introduction = self._interact(
            self.intro_prompt, self.buy_chat_prompt, save_user_message=False)
        return introduction

    def negotiate_buy(self) -> Tuple[Action, Dict[str, Any], Optional[str]]:
        """Take one step in negotiating a purchase.

        Returns:
            action (Action): Next step Action based on user input.
            purchase_info (Dict[str, Any]): Purchase information with keys:
                valid (bool): True if this step concludes a deal, else False.
                good (Good): Good being purchased.
                quantity (int): Quantity of the good being purchased.
                price (float): Price per good being purchased.
            message (Optional[str]): LLM output message, or `None`.

        """
        raw_input = input(f'{self.player.print_money()} > ')
        if clean_string(raw_input) == 'back':
            return Action.BACK, {}, None
        elif clean_string(raw_input) == 'buy':
            return Action.BUY, {}, None
        elif clean_string(raw_input) == 'sell':
            return Action.SELL, {}, None
        elif clean_string(raw_input) == 'inventory':
            return Action.INVENTORY, {}, None
        else:
            output = self._interact(
                raw_input, self.buy_chat_prompt)
            eval_output = self._evaluate_buy(output)

        return Action.BUY_NEGOTIATION, {'valid': False}, output + '\n' + eval_output

    def reset(self, farmer: Farmer) -> None:
        """Reset the model's LLM seed and chat history based on the current
        `farmer`.

        Args:
            farmer (Farmer): Derive the LLM seed from the `farmer` name, and
                use its attributes to populate the `buy_chat_prompt`.

        Returns: None

        """
        self.buy_chat_prompt = self.build_buy_chat_prompt(farmer)

        sha256 = hashlib.sha256()
        sha256.update(farmer.name.encode('utf-8'))
        hash_hex = sha256.hexdigest()
        hash_int = int(hash_hex, 16)
        hash_int_64 = hash_int % (2**64)
        self.seed = hash_int_64
        self.chat_history = []
        return

    def _build_buy_chat_prompt(self, farmer: Farmer) -> str:
        """Build the buy chat prompt from its template and the `farmer` name
        and inventory

        Args:
            farmer (Farmer):

        Returns:
            buy_chat_prompt (str): The buy chat prompt.

        """
        # Convert the `farmer` inventory to a descriptive string
        inventory_str_parts = []
        for good in farmer.goods:
            quantity = farmer.inventory[good]
            if quantity > 0:
                name = good.name
                if quantity != 1:
                    name = self.inflect.plural_noun(name)
                price = farmer.buy_price(good)
                inventory_str_parts.append(f'{quantity} {name}: ${price:.2f}')
        inventory_str = ', '.join(inventory_str_parts)
        buy_chat_prompt = self.buy_chat_prompt_template.replace(
            NAME_TEMPLATE, farmer.name)
        buy_chat_prompt = buy_chat_prompt.replace(
            INVENTORY_TEMPLATE, inventory_str)
        return buy_chat_prompt

    def _evaluate_buy(
            self,
            llm_message: str) -> str:
        """Evaluate a buy negotiation message to see whether a purchase has
        been agreed to.

        Args:
            llm_message (str): Last message produced by the LLM.

        Returns:
            evaluation_message (str): The evaluation message.

        """
        self.increment_seed()

        messages = [
            {'role': 'system', 'content': self.buy_eval_prompt},
            {'role': 'user', 'content': llm_message}
        ]

        request_data = {
            'character': CHARACTER_EVALUATOR,
            'messages': messages,
            'seed': self.seed,
            **self.request_config
        }
        response = requests.post(
            self.url, headers=self.headers, json=request_data, verify=False)
        response_json = response.json()

        if 'choices' in response_json:
            assistant_output = response.json()['choices'][0]['message']['content']
            return assistant_output
        return ''

    def _increment_seed(self) -> None:
        self.seed = (self.seed + 1) % (2**64)
        return

    def _interact(
            self,
            user_message: str,
            system_prompt: str,
            save_user_message: bool = True) -> str:
        """Interact with the LLM, with `message` as the input.

        Args:
            user_message (str): User message to pass to the LLM.
            system_prompt (str): System prompt to guide the LLM's behavior.
            save_user_message (bool): If True, save `message` to
                `self.chat_history`.

        Returns:
            output (str): The LLM's output message.

        """
        self.increment_seed()
        messages = self.chat_history[:] + [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message}
        ]

        if save_user_message:
            self.chat_history.append({'role': 'user', 'content': user_message})

        request_data = {
            "character": CHARACTER_FARMER,
            "messages": messages,
            "seed": self.seed,
            **self.request_config
        }
        response = requests.post(
            self.url, headers=self.headers, json=request_data, verify=False)
        response_json = response.json()

        if 'choices' in response_json:
            output = response.json()['choices'][0]['message']['content']
            output = output.replace('[', '')
            output = output.replace(']', '')
            self.chat_history.append({'role': 'assistant', 'content': output})

        return output




