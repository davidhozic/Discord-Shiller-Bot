"""
    This modules contains definitions related to the client (for API)
"""
from typing import Optional, Union, Optional, List

from . import misc
from . import guild
from . import logging
from . import misc

from .logging.tracing import *

from typeguard import typechecked

import _discord as discord
import asyncio


#######################################################################
# Globals
#######################################################################
LOGIN_TIMEOUT_S = 30
TOKEN_MAX_PRINT_LEN = 5
TASK_SLEEP_DELAY_S = 0.100
TASK_STARTUP_DELAY_S = 2

__all__ = (
    "ACCOUNT",
)


class GLOBALS:
    "Storage class used for storing global variables"
    proxy_installed = False


# ----------------- OPTIONAL ----------------- #
try:
    from aiohttp_socks import ProxyConnector
    GLOBALS.proxy_installed = True
except ImportError:
    GLOBALS.proxy_installed = False
# -------------------------------------------- #

@misc.doc_category("Clients")
class ACCOUNT:
    """
    TODO: update method

    Represents an individual Discord account.
    
    Each ACCOUNT instance runs it's own shilling task.

    Parameters
    ----------
    token : str
        The Discord account's token
    is_user : Optional[bool] =False
        Declares that the ``token`` is a user account token ("self-bot")
    intents: Optional[discord.Intents]=None
        Discord Intents (settings of events that the client will subscribe to)
    proxy: Optional[str]=None
        The proxy to use when connecting to Discord.

        .. IMPORTANT::
            It is **RECOMMENDED** to use a proxy if you are running **MULTIPLE** accounts.
            Running multiple accounts from the same IP address, can result in Discord
            detecting self-bots. 

            Running multiple bot accounts on the other hand is perfectly fine without 
            a proxy.
    servers: Optional[List[guild.GUILD | guild.USER | guild.AutoGUILD]]=[]
        Predefined list of servers (guilds, users, auto-guilds).
    """
    @typechecked
    def __init__(self,
                 token : str,
                 is_user : Optional[bool] =False,
                 intents: Optional[discord.Intents]=None,
                 proxy: Optional[str]=None,
                 servers: Optional[List[Union[guild.GUILD, guild.USER, guild.AutoGUILD]]]=None) -> None:
        self._token = token
        self.is_user = is_user
        self.proxy = proxy
        self.intents = intents

        self._running = False
        self.tasks = {
            "text": None,
            "voice": None
        }
        self._servers: List[guild._BaseGUILD] = []
        self._autoguilds: List[guild.AutoGUILD] = [] # To prevent __eq__ issues, use 2 lists
        if servers is None:
            servers = []

        self._uiservers = servers
        """Temporary list of uninitialized servers
        servers parameter gets stored into _servers to prevent the
        update method from re-initializing initializes objects.
        This gets deleted in the initialize method"""

        connector = None
        if proxy is not None:
            if not GLOBALS.proxy_installed:
                raise ModuleNotFoundError("You need to install extra requirements: pip install discord-advert-framework[proxy]")
        
            connector = ProxyConnector.from_url(proxy)

        self._client = discord.Client(intents=intents, connector=connector)
        misc._write_attr_once(self, "_update_sem", asyncio.Semaphore(2))

    def __eq__(self, other):
        if isinstance(other, ACCOUNT):
            return self._token == other._token
        
        raise NotImplementedError("Only comparison between 2 ACCOUNTs is supported")

    @property
    def running(self) -> bool:
        """
        Is the account still running?

        Returns
        -----------
        True
            The account is logged in and shilling is active.
        False
            The shilling has ended or not begun.
        """
        return self._running
    
    @property
    def servers(self):
        """
        Returns all guild like objects inside the account's s
        shilling list. This also includes :class:`~daf.guild.AutoGUILD`
        """
        return self._servers + self._autoguilds
    
    @property
    def client(self) -> discord.Client:
        "Returns the API wrapper client"
        return self._client

    async def initialize(self):
        """
        Initializes the API wrapper client layer.

        Raises
        ------------
        RuntimeError
            Unable to login to Discord.
        """
        # Login
        trace("[CLIENT:] Logging in...")
        asyncio.create_task(self._client.start(self._token, bot=not self.is_user))
        try:
            await self._client.wait_for("ready", timeout=LOGIN_TIMEOUT_S)
            trace(f"[CLIENT:] Logged in as {self._client.user.display_name}")
        except asyncio.TimeoutError:
            exc = self.tasks["client"].exception()
            raise RuntimeError(f"Error logging in to Discord. (Token {self._token[:TOKEN_MAX_PRINT_LEN]}...)") from exc
        
        for server in self._uiservers:
            try:
                await self.add_server(server)
            except Exception as exc:
                trace(exc, TraceLEVELS.WARNING)

        self._uiservers.clear() # Only needed for predefined initialization

        self.tasks["text"] = asyncio.create_task(self._loop(guild.AdvertiseTaskType.TEXT_ISH))
        self.tasks["voice"] = asyncio.create_task(self._loop(guild.AdvertiseTaskType.VOICE))
        self._running = True

    @typechecked
    async def add_server(self, server: Union[guild.GUILD, guild.USER, guild.AutoGUILD]):
        """
        Initializes a guild like object and
        adds it to the internal account shill list.

        Parameters
        --------------
        server: guild.GUILD | guild.USER | guild.AutoGUILD
            The guild like object to add

        Raises
        --------
        Any
            Raised in 
            :py:meth:`daf.guild.GUILD.initialize()` | :py:meth:`daf.guild.USER.initialize()` | :py:meth:`daf.guild.AutoGUILD.initialize()`
        """
        await server.initialize(parent=self)
        if isinstance(server, guild._BaseGUILD):
            self._servers.append(server)
        else:
            self._autoguilds.append(server)
    
    @typechecked
    def remove_server(self, server: Union[guild.GUILD, guild.USER, guild.AutoGUILD]):
        """
        Removes a guild like object from the shilling list.

        Parameters
        --------------
        server: guild.GUILD | guild.USER | guild.AutoGUILD
            The guild like object to remove
        
        Raises
        -----------
        ValueError
            ``server`` is not in the shilling list.
        """
        if isinstance(server, guild._BaseGUILD):
            self._servers.remove(server)
        else:
            self._autoguilds.remove(server)

    async def close(self):
        """
        Signals the tasks of this account to finish and
        waits for them.
        """
        trace(f"[ACCOUNT:] Logging out of {self.client.user.display_name}...")
        self._running = False
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        await self._client.close()

    async def _loop(self, type_: guild.AdvertiseTaskType):
        """
        Main task loop for advertising thru each guild.
        2 tasks are running as this method.

        Runs while _running is set to True and afterwards
        closes the connection to Discord.

        Parameters
        -------------
        type_:  guild.AdvertiseTaskType
            Task type (for text messages of voice messages)
        """
        while self._running:

            @misc._async_safe("_update_sem")
            async def __loop(self_):
                await asyncio.sleep(TASK_SLEEP_DELAY_S)
                # Sum, creates new list, making modifications on original lists safe
                for server in self.servers:
                    # Remove guild
                    if server._check_state():
                        self.remove_server(server)
                    else:
                        # Async generator that returns message context and guild context of sent messages 
                        # to use in logging
                        async for guild_ctx, message_ctx in server._advertise(type_):
                            # Logging not disabled for guild and message was sent
                            if message_ctx is not None:
                                await logging.save_log(guild_ctx, message_ctx)
                    
                            if not self._running:
                                return
            
            await __loop(self)

    async def update(self, **kwargs):
        """
        Updates the object with new parameters and afterwards updates all lower layers (GUILD->MESSAGE->CHANNEL).

        .. WARNING::
            After calling this method the entire object is reset.
        """
        @misc._async_safe("_update_sem", 2)
        async def update_servers(self_):
            for server in self.servers:
                await server.update(init_options={"parent": self})

        if "token" not in kwargs:
            kwargs["token"] = self._token

        await self.close()
        await misc._update(self, **kwargs)

        await update_servers(self)
