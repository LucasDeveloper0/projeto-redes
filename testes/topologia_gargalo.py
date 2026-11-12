from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

def iniciar_rede():
    # Cria rede com controle de banda/fila (TCLink) e switch autônomo
    net = Mininet(link=TCLink, controller=None)
    h1 = net.addHost('h1')  # Remetente TCP
    h2 = net.addHost('h2')  # Receptor TCP
    s1 = net.addSwitch('s1', failMode='standalone')
    # Link rápido (100 Mbps) no acesso e gargalo (5 Mbps, fila 15) no destino
    net.addLink(h1, s1, bw=100, delay='5ms')
    net.addLink(s1, h2, bw=5, delay='20ms', max_queue_size=15)
    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    iniciar_rede()
