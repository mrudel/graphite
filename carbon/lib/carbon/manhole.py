from twisted.cred import portal, checkers
from twisted.conch.ssh import keys
from twisted.conch.checkers import SSHPublicKeyDatabase
from twisted.conch.manhole import Manhole
from twisted.conch.manhole_ssh import TerminalRealm, ConchFactory
from twisted.internet import reactor
from carbon.conf import settings
from carbon.log import err


namespace = {}


class PublicKeyChecker(SSHPublicKeyDatabase):
  def __init__(self, userKeys):
    self.userKeys = {}
    for username, keyData in userKeys.items():
      self.userKeys[username] = keys.Key.fromString(data=keyData).blob()

  def checkKey(self, credentials):
    if credentials.username in self.userKeys:
      keyBlob = self.userKeys[credentials.username]
      return keyBlob == credentials.blob


def start():
  sshRealm = TerminalRealm()
  sshRealm.chainedProtocolFactory.protocolFactory = lambda _: Manhole(namespace)

  # You can uncomment this if you're lazy and want insecure authentication instead
  # of setting up keys.
  #credChecker = checkers.InMemoryUsernamePasswordDatabaseDontUse(carbon='')
  userKeys = {
    settings.MANHOLE_USER : settings.MANHOLE_PUBLIC_KEY,
  }
  try:
    credChecker = PublicKeyChecker(userKeys)
  except:
    err("failed to load MANHOLE_PUBLIC_KEY")
    return

  sshPortal = portal.Portal(sshRealm)
  sshPortal.registerChecker(credChecker)
  sessionFactory = ConchFactory(sshPortal)
  reactor.listenTCP(settings.MANHOLE_PORT, sessionFactory, interface=settings.MANHOLE_INTERFACE)
