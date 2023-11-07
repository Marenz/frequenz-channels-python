# License: MIT
# Copyright © 2022 Frequenz Energy-as-a-Service GmbH

"""Frequenz Channels.

This package contains
[channel](https://en.wikipedia.org/wiki/Channel_(programming)) implementations.

Channels:

* [Anycast][frequenz.channels.Anycast]: A channel that supports multiple
  senders and multiple receivers.  A message sent through a sender will be
  received by exactly one receiver.

* [Broadcast][frequenz.channels.Broadcast]: A channel to broadcast messages
  from multiple senders to multiple receivers. Each message sent through any of
  the senders is received by all of the receivers.

Other base classes:

* [Receiver][frequenz.channels.Receiver]: An object that can wait for and
  consume messages from a channel.

* [Sender][frequenz.channels.Sender]: An object that can send messages to
  a channel.

Utilities:

* [util][frequenz.channels.util]: A module with utilities, like special
  receivers that implement timers, file watchers, merge receivers, or wait for
  messages in multiple channels.

Exception classes:

* [Error][frequenz.channels.Error]: Base class for all errors in this
  library.

* [ChannelError][frequenz.channels.ChannelError]: Base class for all errors
  related to channels.

* [ChannelClosedError][frequenz.channels.ChannelClosedError]: Error raised when
  trying to operate (send, receive, etc.) through a closed channel.

* [SenderError][frequenz.channels.SenderError]: Base class for all errors
  related to senders.

* [ReceiverError][frequenz.channels.ReceiverError]: Base class for all errors
  related to receivers.

* [ReceiverStoppedError][frequenz.channels.ReceiverStoppedError]: A receiver
  stopped producing messages.
"""

from . import util
from ._anycast import Anycast
from ._broadcast import Broadcast
from ._exceptions import ChannelClosedError, ChannelError, Error
from ._receiver import Receiver, ReceiverError, ReceiverStoppedError
from ._sender import Sender, SenderError

__all__ = [
    "Anycast",
    "Broadcast",
    "ChannelClosedError",
    "ChannelError",
    "Error",
    "Receiver",
    "ReceiverError",
    "ReceiverStoppedError",
    "Sender",
    "SenderError",
    "util",
]
