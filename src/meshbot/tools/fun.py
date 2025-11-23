"""Fun and interactive tools."""

import logging
from typing import Any

from pydantic_ai import RunContext

from .logging_wrapper import create_logging_tool_decorator

logger = logging.getLogger(__name__)


def register_fun_tools(agent: Any) -> None:
    """Register fun/interactive tools.

    Args:
        agent: The Pydantic AI agent to register tools with
    """
    # Create logging tool decorator
    tool = create_logging_tool_decorator(agent)

    @tool()
    async def roll_dice(ctx: RunContext[Any], count: int = 1, sides: int = 6) -> str:
        """Roll dice and return the results.

        Args:
            count: Number of dice to roll (1-10)
            sides: Number of sides per die (2-100)

        Returns:
            Dice roll results
        """
        try:
            import random

            # Validate inputs
            if not 1 <= count <= 10:
                return "Please roll between 1 and 10 dice"
            if not 2 <= sides <= 100:
                return "Dice must have between 2 and 100 sides"

            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls)

            if count == 1:
                return f"Rolled 1d{sides}: {rolls[0]}"
            else:
                rolls_str = ", ".join(map(str, rolls))
                return f"Rolled {count}d{sides}: [{rolls_str}] = {total}"
        except Exception as e:
            logger.error(f"Error rolling dice: {e}")
            return "Error rolling dice"

    @tool()
    async def flip_coin(ctx: RunContext[Any]) -> str:
        """Flip a coin and return the result.

        Returns:
            Either "Heads" or "Tails"
        """
        try:
            import random

            result = random.choice(["Heads", "Tails"])
            return f"Coin flip: {result}"
        except Exception as e:
            logger.error(f"Error flipping coin: {e}")
            return "Error flipping coin"

    @tool()
    async def random_number(
        ctx: RunContext[Any],
        min_value: int = 1,
        max_value: int = 100,
    ) -> str:
        """Generate a random number within a range.

        Args:
            min_value: Minimum value (inclusive)
            max_value: Maximum value (inclusive)

        Returns:
            Random number in the specified range
        """
        try:
            import random

            if min_value >= max_value:
                return "Min value must be less than max value"

            if max_value - min_value > 1000000:
                return "Range too large (max 1 million)"

            result = random.randint(min_value, max_value)
            return f"Random number ({min_value}-{max_value}): {result}"
        except Exception as e:
            logger.error(f"Error generating random number: {e}")
            return "Error generating random number"

    @tool()
    async def magic_8ball(ctx: RunContext[Any], question: str) -> str:
        """Ask the magic 8-ball a yes/no question.

        Args:
            question: Your yes/no question

        Returns:
            Magic 8-ball response
        """
        try:
            import random

            responses = [
                # Positive
                "It is certain",
                "It is decidedly so",
                "Without a doubt",
                "Yes definitely",
                "You may rely on it",
                "As I see it, yes",
                "Most likely",
                "Outlook good",
                "Yes",
                "Signs point to yes",
                # Non-committal
                "Reply hazy, try again",
                "Ask again later",
                "Better not tell you now",
                "Cannot predict now",
                "Concentrate and ask again",
                # Negative
                "Don't count on it",
                "My reply is no",
                "My sources say no",
                "Outlook not so good",
                "Very doubtful",
            ]

            response = random.choice(responses)
            return f"🎱 {response}"
        except Exception as e:
            logger.error(f"Error with magic 8-ball: {e}")
            return "The magic 8-ball is cloudy"
