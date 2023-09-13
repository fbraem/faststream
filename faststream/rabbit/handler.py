from typing import Callable, Optional, Sequence

import aio_pika
from fast_depends.core import CallModel

from faststream._compat import override
from faststream.broker.handler import AsyncHandler
from faststream.broker.middlewares import BaseMiddleware
from faststream.broker.parsers import resolve_custom_func
from faststream.broker.types import (
    CustomDecoder,
    CustomParser,
    Filter,
    P_HandlerParams,
    T_HandlerReturn,
)
from faststream.broker.wrapper import HandlerCallWrapper
from faststream.rabbit.helpers import RabbitDeclarer
from faststream.rabbit.message import RabbitMessage
from faststream.rabbit.parser import AioPikaParser
from faststream.rabbit.shared.schemas import (
    BaseRMQInformation,
    RabbitExchange,
    RabbitQueue,
)
from faststream.types import AnyDict


class LogicHandler(AsyncHandler[aio_pika.IncomingMessage], BaseRMQInformation):
    """A class to handle logic for RabbitMQ message consumption.

    Attributes:
        queue : RabbitQueue object representing the queue to consume from
        exchange : Optional RabbitExchange object representing the exchange to bind the queue to
        consume_args : Additional arguments to pass when consuming from the queue
        _consumer_tag : Optional string representing the consumer tag
        _queue_obj : Optional aio_pika.RobustQueue object representing the declared queue

    Methods:
        __init__ : Initializes the LogicHandler object
        add_call : Adds a call to be handled by the LogicHandler
        start : Starts consuming messages from the queue
        close : Closes the consumer and cancels message consumption
    !!! note

        The above docstring is autogenerated by docstring-gen library (https://docstring-gen.airt.ai)
    """

    queue: RabbitQueue
    exchange: Optional[RabbitExchange]
    consume_args: AnyDict

    _consumer_tag: Optional[str]
    _queue_obj: Optional[aio_pika.RobustQueue]

    def __init__(
        self,
        queue: RabbitQueue,
        # RMQ information
        exchange: Optional[RabbitExchange] = None,
        consume_args: Optional[AnyDict] = None,
        # AsyncAPI information
        description: Optional[str] = None,
        title: Optional[str] = None,
    ):
        """Initialize a RabbitMQ consumer.

        Args:
            queue: RabbitQueue object representing the queue to consume from
            exchange: RabbitExchange object representing the exchange to bind the queue to (optional)
            consume_args: Additional arguments for consuming from the queue (optional)
            description: Description of the consumer (optional)
            title: Title of the consumer (optional)
        !!! note

            The above docstring is autogenerated by docstring-gen library (https://docstring-gen.airt.ai)
        """
        super().__init__(
            description=description,
            title=title,
        )

        self.queue = queue
        self.exchange = exchange
        self.consume_args = consume_args or {}

        self._consumer_tag = None
        self._queue_obj = None

    def add_call(
        self,
        *,
        handler: HandlerCallWrapper[
            aio_pika.IncomingMessage, P_HandlerParams, T_HandlerReturn
        ],
        dependant: CallModel[P_HandlerParams, T_HandlerReturn],
        parser: Optional[CustomParser[aio_pika.IncomingMessage]],
        decoder: Optional[CustomDecoder[aio_pika.IncomingMessage]],
        filter: Filter[RabbitMessage],
        middlewares: Optional[
            Sequence[Callable[[aio_pika.IncomingMessage], BaseMiddleware]]
        ],
    ) -> None:
        """Add a call to the handler.

        Args:
            handler: The handler for the call.
            dependant: The dependant for the call.
            parser: Optional custom parser for the call.
            decoder: Optional custom decoder for the call.
            filter: The filter for the call.
            middlewares: Optional sequence of middlewares for the call.

        Returns:
            None
        !!! note

            The above docstring is autogenerated by docstring-gen library (https://docstring-gen.airt.ai)
        """
        super().add_call(
            handler=handler,
            parser=resolve_custom_func(parser, AioPikaParser.parse_message),
            decoder=resolve_custom_func(decoder, AioPikaParser.decode_message),
            filter=filter,  # type: ignore[arg-type]
            dependant=dependant,
            middlewares=middlewares,
        )

    @override
    async def start(self, declarer: RabbitDeclarer) -> None:  # type: ignore[override]
        """Starts the consumer for the RabbitMQ queue.

        Args:
            declarer: RabbitDeclarer object used to declare the queue and exchange

        Returns:
            None
        !!! note

            The above docstring is autogenerated by docstring-gen library (https://docstring-gen.airt.ai)
        """
        self._queue_obj = queue = await declarer.declare_queue(self.queue)

        if self.exchange is not None:
            exchange = await declarer.declare_exchange(self.exchange)
            await queue.bind(
                exchange,
                routing_key=self.queue.routing,
                arguments=self.queue.bind_arguments,
            )

        self._consumer_tag = await queue.consume(
            # NOTE: aio-pika expects AbstractIncomingMessage, not IncomingMessage
            self.consume,  # type: ignore[arg-type]
            arguments=self.consume_args,
        )

    async def close(self) -> None:
        if self._queue_obj is not None:
            if self._consumer_tag is not None:  # pragma: no branch
                await self._queue_obj.cancel(self._consumer_tag)
                self._consumer_tag = None
            self._queue_obj = None