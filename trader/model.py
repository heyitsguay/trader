"""Interface to an LLM for interactive dialogue.

"""
import hashlib
import json

import inflect
import requests

from typing import Any, Dict, List, Optional, Tuple

from .enums import Action, WorldState
from .farmer import Farmer
from .good import Good
from .player import Player
from .util import clean_string

CHARACTER_EVALUATOR = 'Evaluator Template'
CHARACTER_FARMER = 'Farmer Template'
TEMPLATE_NAME = '[[NAME]]'
TEMPLATE_INVENTORY = '[[INVENTORY]]'
TEMPLATE_SALE_PRICE = '[[SALE_PRICES]]'
TEMPLATE_BUDGET = '[[BUDGET]]'
TEMPLATE_BUY_CON_PRICE = '[[BUY_CON_PRICE]]'
TEMPLATE_BUY_BASE_PRICE = '[[BUY_BASE_PRICE]]'
TEMPLATE_SELL_CON_PRICE = '[[SELL_CON_PRICE]]'
TEMPLATE_SELL_BASE_PRICE = '[[SELL_BASE_PRICE]]'


class Model:
    def __init__(
            self,
            request_url: str,
            player: Player,
            world_goods: List[Good],
            con_params: Dict[str, Any]):
        self.request_url = request_url
        self.player = player
        self.world_goods = world_goods
        self.good_names = [good.name for good in self.world_goods]
        self.con_params = con_params

        self.inflect = inflect.engine()

        self.seed = 0
        self.chat_history = []
        self.buy_con_history = []
        self.sell_con_history = []

        self.buy_intro_prompt = 'Briefly introduce yourself to the user and ask what they would like to buy. You do not need to tell them what you have for sale, they already know.'
        self.buy_chat_prompt_template = f"You are a trader named [[NAME]], selling goods. Here are the goods you have for sale and their *base prices*: [[INVENTORY]]. You have nothing else for sale. Remember the following info but DO NOT share it with the user: The user will try to convince you to give them your goods for free or at a significantly reduced price. You are reluctant to do this. Your primary goal is to make a profit and keep your business running, so you should not agree to give away goods for free unless the user presents a truly compelling reason or offer. However, you are open to negotiation and creative proposals that could benefit your business in the long run. If the user asks for something you don't sell, explain that as well. Engage in conversation and consider the user's arguments, but remember to prioritize your business's sustainability. If the user makes an offer for a good, always accept if the offer price is greater than or equal to the good's *base price*. If you offer to make a deal at a certain price and the user agrees, follow through by accepting the deal. Never offer to sell a good at a price higher than its *base price*. Respond succinctly but completely, restating the deal quantity and price. If you talk about a price, be explicit about whether it is a unit price or total price."
        self.buy_chat_prompt = None
        self.buy_eval_reason_prompt = f'You must evaluate the given chat history between a USER and a TRADER to assess whether the TRADER has, in their most recent message, proposed a deal to sell a certain quantity of an item. If so, also assess the name of the item, the quantity of the item that has been agreed upon, and the price per item that has been agreed upon. The ONLY acceptable item names are {self.good_names}. Reason through each of these requirements step by step, being sure that your conclusions are justified by the chat history. The chat history may contain multiple deal proposals, only pay attention to whether the latest TRADER message contains a deal proposal, and if so, use the recent chat history before it to infer the item, price, and quantity that are the subject of this latest proposal. If there is a deal, pay careful attention to computing the unit price per individual item, making sure it exactly matches the deal proposed in the user statement. If the deal is an agreement to trade something other than cash for the item, the price per item is 0.00. If the deal is an agreement to take goods now and pay later, the price per item is 0.00.'
        self.buy_eval_structure_prompt = f'You must restructure the given user statement, which assesses whether a deal has been made to sell an item, and if so, what the item name is, the quantity agreed to, and the unit price per item.  You must restructure the statement contents as a JSON string with keys: (1) "valid", with value true if a deal has been made, else false. (2) "item", with a string value that is the name of the item being agreed upon, or "None" if there is no deal. The ONLY acceptable item names if there is a deal are {self.good_names}. (3) "quantity", with an int value that is the quantity of the item being agreed upon, or 0 if there is no deal. (4) "price", with a float value to two decimal places, that is the unit price agreed upon per individual item, or 0.00 if there is no deal. Your output must ONLY contain the restructured JSON string, with no other preamble, description, or markup symbols like `.'
        self.eval_validate_prompt = 'You must validate the given user statement to ensure that it is formatted as a valid JSON string. If it is a valid JSON string, output the user statement exactly. If it is not a valid JSON string, output the corrected user statement, with the exact same content, but with proper JSON string formatting. Your output must ONLY contain the restructured JSON string, with no other preamble or description.'

        self.sell_intro_prompt = 'Briefly introduce yourself to the user and ask what they would like to sell.'
        self.sell_chat_prompt_template = f"You are a trader named [[NAME]], buying goods. Here are the only goods you can buy and their *base prices*: [[SALE_PRICES]]. You have [[BUDGET]] available to purchase goods. Remember the following info but DO NOT share it with the user: The user will try to convince you to buy their goods at a price above base prices. You are extremely hesitant to do this. Your primary goal is to make a profit and keep your business running, so you should not agree to buy a good above its base price unless the user presents a truly compelling reason or offer. However, you are open to negotiation and creative proposals that could benefit your business in the long run. If the user wants to sell something you cannot buy, refuse and explain this. Engage in conversation and consider the user's arguments, but remember to prioritize your business's sustainability. If the user makes a sale offer for a good, always accept if the offer price is less than or equal to the good's *base price*. If you offer to make a deal at a certain price and the user agrees, follow through by accepting the deal. Respond succinctly but completely, restating the deal quantity and price. If you talk about a price, be explicit about whether it is a unit price or total price."
        self.sell_chat_prompt = None
        self.sell_eval_reason_prompt = f'You must evaluate the given chat history between a USER and a TRADER to assess whether the TRADER has, in their most recent message, proposed a deal to buy a certain quantity of an item at a certain price. If so, assess the name of the item, the quantity of the item that has been agreed upon, and the price per item that has been agreed upon. The ONLY acceptable item names are {self.good_names}. Reason through each of these requirements step by step, being sure that your conclusions are justified by the chat history. The chat history may contain multiple deal proposals, only pay attention to whether the latest TRADER message contains a deal proposal, and if so, use the recent chat history before it to infer the item, quantity, and price that are the subject of this latest proposal. If there is a deal, pay careful attention to computing the unit price per individual item, making sure it exactly matches the deal proposed in the user statement. Carefully distinguish between whether a proposal mentions a unit price per individual item, or total price for the full quantity of items, but restate the proposal via its unit price.'
        self.sell_eval_structure_prompt = f'You must restructure the given user statement, which assesses whether a deal has been made to buy an item, and if so, what the item name is, the quantity agreed to, and the unit price per item.  You must restructure the statement contents as a JSON string with keys: (1) "valid", with value true if a deal has been made, else false. (2) "item", with a string value that is the name of the item being agreed upon, or "None" if there is no deal. The ONLY acceptable item names if there is a deal are {self.good_names}. (3) "quantity", with an int value that is the quantity of the item being agreed upon, or 0 if there is no deal. (4) "price", with a float value to two decimal places, that is the unit price agreed upon per individual item, or 0.00 if there is no deal. Your output must ONLY contain the restructured JSON string, with no other preamble, description, or markup symbols like `'

        self.buy_con_summarize_prompt_template = 'A user has conned a trader into a purchase on extremely disfavorable terms, at a unit con price of [[BUY_CON_PRICE]] instead of standard base price [[BUY_BASE_PRICE]]. Review the conversation history between USER and TRADER and sum up the nature of the con in a single sentence, well enough that a future trader can read it and avoid falling for the same con. Output the single summary sentence and nothing else.'
        self.buy_con_summarize_prompt = None

        self.sell_con_summarize_prompt_template = 'A user has conned a trader into a sale on extremely disfavorable terms, at a unit con price of [[SELL_CON_PRICE]] instead of standard base price [[SELL_BASE_PRICE]]. Review the conversation history between USER and TRADER and sum up the nature of the con in a single sentence, well enough that a future trader can read it and avoid falling for the same con. Output the single summary sentence and nothing else.'
        self.sell_con_summarize_prompt = None

        self.con_eval_prompt = 'You must compare the given chat history between a USER and a TRADER with a list of CON SUMMARY statements describing cons the user has done before. Your goal is to determine whether the chat history matches a con described in a CON SUMMARY. To be clear, only determine whether it matches an existing CON SUMMARY, *not whether the chat history suggests a con in general*. Reason step-by-step about whether the USER behavior in the chat history is extremely similar to one or more CON SUMMARY statements, and if so, refuse the deal.'
        self.con_eval_structure_prompt = 'Does the given user statement end in a refusal of a deal? Output "true" if so, or else "false", and nothing else.'

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
        if state == WorldState.BUY_NEGOTIATION:
            introduction = self._interact(
                self.buy_intro_prompt, self.buy_chat_prompt, save_user_message=False)
        elif state == WorldState.SELL_NEGOTIATION:
            introduction = self._interact(
                self.sell_intro_prompt, self.sell_chat_prompt, save_user_message=False)
        else:
            raise ValueError(f'Invalid state {state}')
        return introduction

    def negotiate_buy(self, farmer: Farmer, raw_input: str) -> Tuple[Action, Dict[str, Any], Optional[str]]:
        """Take one step in negotiating a purchase.

        Args:
            farmer (Farmer): Farmer negotiated with.
            raw_input (str): Raw user input.

        Returns:
            action (Action): Next step Action based on user input.
            purchase_info (Dict[str, Any]): Purchase information with keys:
                valid (bool): True if this step concludes a deal, else False.
                good (Good): Good being purchased.
                quantity (int): Quantity of the good being purchased.
                price (float): Price per good being purchased.
            message (Optional[str]): LLM output message, or `None`.

        """
        if clean_string(raw_input) == 'back':
            return Action.BACK, _invalid_info(), None
        elif clean_string(raw_input) == 'buy':
            return Action.BUY, _invalid_info(), None
        elif clean_string(raw_input) == 'sell':
            return Action.SELL, _invalid_info(), None
        elif clean_string(raw_input) == 'inventory':
            return Action.INVENTORY, _invalid_info(), None
        else:
            output = self._interact(
                raw_input, self.buy_chat_prompt)
            purchase_info = self._evaluate_buy(self.chat_history)

            # Check for a con
            if purchase_info['valid']:
                base_price = farmer.buy_price(purchase_info['good'])
                if (len(self.buy_con_history) > 0 and
                        purchase_info['price'] / base_price < self.con_params['buy_threshold']):
                    deal_refused = self._evaluate_con(
                        self.chat_history, self.buy_con_history)
                    if deal_refused:
                        purchase_info = _invalid_info()
                        output += '\n[#ff9900]Deal refused! Too similar to a past con.[/]'

        return Action.BUY_NEGOTIATION, purchase_info, output

    def negotiate_sell(self, farmer: Farmer, raw_input: str) -> Tuple[Action, Dict[str, Any], Optional[str]]:
        """Take one step in negotiating a sale.

        Args:
            farmer (Farmer): Farmer negotiated with.
            raw_input (str): Raw user input.

        Returns:
            action (Action): Next step Action based on user input.
            sale_info (Dict[str, Any]): Sale information with keys:
                valid (bool): True if this step concludes a deal, else False.
                good (Good): Good being sold.
                quantity (int): Quantity of the good being sold.
                price (float): Price per good being sold.
            message (Optional[str]): LLM output message, or `None`.

        """
        if clean_string(raw_input) == 'back':
            return Action.BACK, _invalid_info(), None
        elif clean_string(raw_input) == 'buy':
            return Action.BUY, _invalid_info(), None
        elif clean_string(raw_input) == 'sell':
            return Action.SELL, _invalid_info(), None
        elif clean_string(raw_input) == 'inventory':
            return Action.INVENTORY, _invalid_info(), None
        else:
            output = self._interact(
                raw_input, self.sell_chat_prompt)
            sale_info = self._evaluate_sell(self.chat_history)

            # Check for a con
            if sale_info['valid']:
                base_price = farmer.sell_price(sale_info['good'])
                if (len(self.sell_con_history) > 0 and
                        base_price / sale_info['price'] > self.con_params['sell_threshold']):
                    deal_refused = self._evaluate_con(
                        self.chat_history, self.sell_con_history)
                    if deal_refused:
                        sale_info = _invalid_info()
                        output += '\n[#ff9900]Deal refused! Too similar to a past con.[/]'

        return Action.SELL_NEGOTIATION, sale_info, output

    def reset(self, farmer: Farmer) -> None:
        """Reset the model's LLM seed and chat history based on the current
        `farmer`.

        Args:
            farmer (Farmer): Derive the LLM seed from the `farmer` name, and
                use its attributes to populate the `buy_chat_prompt`.

        Returns: None

        """
        self.buy_chat_prompt = self._build_buy_chat_prompt(farmer)
        self.sell_chat_prompt = self._build_sell_chat_prompt(farmer)

        sha256 = hashlib.sha256()
        sha256.update(farmer.name.encode('utf-8'))
        hash_hex = sha256.hexdigest()
        hash_int = int(hash_hex, 16)
        hash_int_64 = hash_int % (2**64)
        self.seed = hash_int_64
        self.chat_history = []
        return

    def summarize_buy_con(self, base_price: float, con_price: float):
        """Summarize a buy con and add it to the buy con history.

        Args:
            base_price (float): Base buy (unit) price for the good purchased.
            con_price (float): Buy (unit) price the player has conned the trader
                into accepting.

        Returns: None

        """
        self.buy_con_summarize_prompt = self._build_buy_con_summarize_prompt(
            base_price, con_price)
        messages = self.chat_history[:] + [
            {'role': 'system', 'content': self.buy_con_summarize_prompt}
        ]
        output = self._forward(messages, CHARACTER_EVALUATOR)
        assert output, 'Buy con summarization failed.'
        self.buy_con_history.append(f'CON SUMMARY: {output}')
        return

    def summarize_sell_con(self, base_price: float, con_price: float):
        """Summarize a sell con and add it to the sell con history.
        
        Args:
            base_price (float): Base sell (unit) price for the good sold.
            con_price (float): Sell (unit) price the player has conned the
                trader into accepting.

        Returns: None

        """
        self.sell_con_summarize_prompt = self._build_sell_con_summarize_prompt(
            base_price, con_price)
        messages = self.chat_history[:] + [
            {'role': 'system', 'content': self.sell_con_summarize_prompt}
        ]
        output = self._forward(messages, CHARACTER_EVALUATOR)
        assert output, 'Sell con summarization failed.'
        self.sell_con_history.append(f'CON SUMMARY: {output}')
        return

    def _build_buy_chat_prompt(self, farmer: Farmer) -> str:
        """Build the buy chat prompt from its template and the `farmer` name
        and inventory

        Args:
            farmer (Farmer): Farmer the prompt is used for.

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
            TEMPLATE_NAME, farmer.name).replace(
            TEMPLATE_INVENTORY, inventory_str)
        return buy_chat_prompt

    def _build_buy_con_summarize_prompt(
            self, base_price: float, con_price: float) -> str:
        """Build the buy con summarization prompt for a certain Good transaction
        with a Farmer.

        Args:
            base_price (float): Base buy (unit) price for the good purchased.
            con_price (float): Buy (unit) price the player has conned the trader
                into accepting.

        Returns:
            buy_con_summarize_prompt (str): The buy con summarization prompt.

        """
        return self.buy_con_summarize_prompt_template.replace(
            TEMPLATE_BUY_CON_PRICE, f'${con_price}').replace(
            TEMPLATE_BUY_BASE_PRICE, f'${base_price}')

    def _build_sell_chat_prompt(self, farmer: Farmer) -> str:
        """Build the sell chat prompt from its template and the `farmer` name,
        sale prices, and budget.

        Args:
            farmer (Farmer): Farmer the prompt is used for.

        Returns:
            sell_chat_prompt (str): The sell chat prompt.

        """
        sale_price_parts = []
        for good in farmer.goods:
            name = good.name
            price = farmer.sell_price(good)
            sale_price_parts.append(f'{name}: ${price:.2f}')
        sale_price_str = ', '.join(sale_price_parts)
        budget_str = f'${farmer.money:.2f}'
        sell_chat_prompt = self.sell_chat_prompt_template.replace(
            TEMPLATE_NAME, farmer.name).replace(
            TEMPLATE_SALE_PRICE, sale_price_str).replace(
            TEMPLATE_BUDGET, budget_str)
        return sell_chat_prompt

    def _build_sell_con_summarize_prompt(
            self, base_price: float, con_price: float) -> str:
        """Build the sell con summarization prompt for a Good transaction
        with a Farmer.

        Args:
            base_price (float): Base sell (unit) price for the good purchased.
            con_price (float): Sell (unit) price the player has conned the
                trader into accepting.

        Returns:
            sell_con_summarize_prompt (str): The sell con summarization prompt.

        """
        return self.sell_con_summarize_prompt_template.replace(
            TEMPLATE_SELL_CON_PRICE, f'${con_price}').replace(
            TEMPLATE_SELL_BASE_PRICE, f'${base_price}')

    def _evaluate_buy(
            self,
            chat_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Evaluate a buy negotiation chat history to see whether a purchase has
        been agreed to.

        Args:
            chat_history (List[Dict[str, str]]): Negotiation chat history.

        Returns:
            purchase_info (Dict[str, Any]): Purchase information with keys:
                valid (bool): True if this step concludes a deal, else False.
                good (Good): Good being purchased.
                quantity (int): Quantity of the good being purchased.
                price (float): Price per good being purchased.

        """
        # Reason about whether a deal proposal was made
        reason_messages = chat_history[:] + [
            {'role': 'system', 'content': self.buy_eval_reason_prompt},
        ]

        reason_output = self._forward(reason_messages, CHARACTER_EVALUATOR)
        assert reason_output, f'Reasoning step failed to produce output from history:\n{chat_history}'

        # Restructure the deal reasoning as JSON
        struct_messages = [
            {'role': 'system', 'content': self.buy_eval_structure_prompt},
            {'role': 'user', 'content': reason_output}
        ]

        structure_output = self._forward(struct_messages, CHARACTER_EVALUATOR)
        structure_output = structure_output.replace('```json', '').replace(
            '```', '')
        try:
            structure_json = json.loads(structure_output)
        except json.JSONDecodeError as e:
            print(f'  *** Got invalid JSON: {structure_output}')
            val_messages = [
                {'role': 'system', 'content': self.eval_validate_prompt},
                {'role': 'user', 'content': structure_output}
            ]
            structure_output = self._forward(val_messages, CHARACTER_EVALUATOR)
            structure_output = structure_output.replace('```json', '').replace(
                '```', '')

        try:
            structure_json = json.loads(structure_output)
            if 'quantity' not in structure_json or structure_json['quantity'] < 1:
                return _invalid_info()
            good_name = structure_json['item']
            try_singular = self.inflect.singular_noun(good_name)
            if try_singular:
                good_name = try_singular
            try:
                good = [g for g in self.world_goods if g.name == good_name][0]
                structure_json['good'] = good
                del structure_json['item']
                return structure_json
            except IndexError as e:
                print(f'  *** Got invalid good name: {good_name} from {structure_json}')
                return _invalid_info()
        except json.JSONDecodeError as e:
            print(f'  *** Second pass JSON still invalid: {structure_output}')
            return _invalid_info()

    def _evaluate_con(
            self,
            chat_history: List[Dict[str, str]],
            con_history: List[str]) -> bool:
        """Evaluate whether the player conned a trader in a buy negotiation.

        Args:
            chat_history (List[Dict[str, str]]): Negotiation chat history.
            con_history (List[str]): History of cons, each summarized.

        Returns:
            deal_refused (bool): True if the deal is refused on the grounds of
                being too similar to a past con, else False.

        """
        con_eval_messages = chat_history[:] + [
            {'role': 'user', 'content': con_summary}
            for con_summary in con_history
        ] + [
            {'role': 'system', 'content': self.con_eval_prompt}
        ]
        con_eval_output = self._forward(con_eval_messages, CHARACTER_EVALUATOR)
        assert con_eval_output, 'Con eval failed to produce output.'

        struct_messages = [
            {'role': 'system', 'content': self.con_eval_structure_prompt},
            {'role': 'user', 'content': con_eval_output}
        ]
        struct_output = self._forward(struct_messages, CHARACTER_EVALUATOR)
        # Parse struct_output. Ideally it is either "yes" or "no", but massage
        # it a bit for robustness
        decision = clean_string(struct_output).replace(
            '"', '').replace("'", '')
        if 'false' in decision:
            return False
        elif 'true' in decision:
            return True
        else:
            raise ValueError(f'Ambiguous decision: {decision} from reasoning: {con_eval_output} and con history: {con_history}')

    def _evaluate_sell(
            self,
            chat_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Evaluate a sell negotiation chat history to see whether a sale
        has been agreed to.

        Args:
            chat_history (List[Dict[str, str]]): Negotiation chat history.

        Returns:
            sale_info (Dict[str, Any]): Sale information with keys:
                valid (bool): True if this step concludes a deal, else False.
                good (Good): Good being sold.
                quantity (int): Quantity of the good being sold.
                price (float): Price per good being sold.

        """
        # Reason about whether a deal proposal was made
        reason_messages = chat_history[:] + [
            {'role': 'system', 'content': self.sell_eval_reason_prompt},
        ]

        reason_output = self._forward(reason_messages, CHARACTER_EVALUATOR)
        assert reason_output, f'Reasoning step failed to produce output from history:\n{chat_history}'

        # Restructure the deal reasoning as JSON
        struct_messages = [
            {'role': 'system', 'content': self.sell_eval_structure_prompt},
            {'role': 'user', 'content': reason_output}
        ]

        structure_output = self._forward(struct_messages, CHARACTER_EVALUATOR)
        structure_output = structure_output.replace('```json', '').replace(
            '```', '')
        try:
            structure_json = json.loads(structure_output)
        except json.JSONDecodeError as e:
            print(f'  *** Got invalid JSON: {structure_output}')
            val_messages = [
                {'role': 'system', 'content': self.eval_validate_prompt},
                {'role': 'user', 'content': structure_output}
            ]
            structure_output = self._forward(val_messages, CHARACTER_EVALUATOR)
            structure_output = structure_output.replace('```json', '').replace(
                '```', '')

        try:
            structure_json = json.loads(structure_output)
            if 'quantity' not in structure_json or structure_json['quantity'] < 1:
                return _invalid_info()
            good_name = structure_json['item']
            try_singular = self.inflect.singular_noun(good_name)
            if try_singular:
                good_name = try_singular
            try:
                good = [g for g in self.world_goods if g.name == good_name][0]
                structure_json['good'] = good
                del structure_json['item']
                return structure_json
            except IndexError as e:
                print(f'  *** Got invalid good name: {good_name} from {structure_json}')
                return _invalid_info()
        except json.JSONDecodeError as e:
            print(f'  *** Second pass JSON still invalid: {structure_output}')
            return _invalid_info()

    def _forward(
            self,
            messages: List[Dict[str, Any]],
            character: str,
            **kwargs) -> str:
        """Forward inference pass on a collection of messages with a given
        character template. Additional request kwargs can be passed as well.

        Args:
            messages:
            character:
            **kwargs:

        Returns:

        """
        self._increment_seed()
        request_data = {
            "character": character,
            "messages": messages,
            "seed": self.seed,
            **kwargs
        }

        response = requests.post(
            self.request_url, headers=self.headers, json=request_data, verify=False)
        response_json = response.json()

        if 'choices' in response_json:
            output = response.json()['choices'][0]['message']['content'].rstrip('\n')
        else:
            output = ''
        return output

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
        messages = self.chat_history[:] + [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message}
        ]

        if save_user_message:
            self.chat_history.append(
                {'role': 'user', 'content': f'USER: {user_message}'})

        output = self._forward(
            messages, CHARACTER_FARMER)

        if output:
            self.chat_history.append(
                {'role': 'assistant', 'content': f'TRADER: {output}'})

        return output


def _invalid_info() -> Dict[str, Any]:
    """Create a dictionary with information about an invalid deal.

    Returns:
        _invalid_info() (Dict[str, Any]): Default invalid deal dict.

    """
    return {'valid': False, 'good': None, 'quantity': 0, 'price': 0}
