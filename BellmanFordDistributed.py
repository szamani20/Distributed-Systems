import socket
import threading
from time import sleep
import json

BASE_PORT = 5000


class Message:
    def __init__(self, src_id, w_until_node, w_link):
        self.src_id = src_id  # Sender Node id
        self.w_until_node = w_until_node  # Weight sum from sender node to source node (0)
        self.w_link = w_link  # Weight of the link

    def __str__(self):
        return '{} {} {}'.format(self.src_id, self.w_until_node, self.w_link)


class Edge:
    def __init__(self, weight, delay, receiving_port):
        self.weight = weight  # Weight of the edge
        self.delay = delay  # Send delay of the link
        self.receiving_port = receiving_port
        self.sending_socket = socket.socket()  # From source node of edge
        self.receiver_socket = socket.socket()  # To destination node of edge

    def __str__(self):
        return str(self.weight)


class Node:
    def __init__(self, node_id):
        self.node_id = node_id  # Starts from 0 to graph_size-1
        self.in_edges = []  # Edges into this Node
        self.out_edges = []  # Edges from this Node
        self.parent = None  # Parent (node_id) in route to source
        self.dist = float('Inf')  # Distance from source node
        if node_id == 0:  # Source node
            self.dist = 0  # Distance from self is 0
            self.parent = -1  # To specify the source node

    def init_sender_socket(self, receiving_port, e):
        # Alt: use a variable to show if connected
        # Alt: call connect on all sockets after creating the network
        sleep(0.2)
        e.sending_socket.connect((socket.gethostname(), receiving_port))

    def init_receiver_socket(self, host, port, e):
        e.receiver_socket.bind((host, port))
        e.receiver_socket.listen()
        sender_connection_socket, address = e.receiver_socket.accept()

        while True:
            data = sender_connection_socket.recv(1024).decode()
            if not data:
                break
            m = Message(**json.loads(data, encoding='utf-8'))
            print('in node {} received'.format(self.node_id), m)

            if m.w_until_node + m.w_link < self.dist:
                self.dist = m.w_until_node + m.w_link
                self.parent = m.src_id
                self.update()

    def send_data(self, message, e):
        threading.Thread(target=self._send_data, args=(message, e)).start()

    def _send_data(self, message, e):
        sleep(e.delay)
        e.sending_socket.sendall(json.dumps(message.__dict__).encode('utf-8'))

    def add_out_edge(self, e):
        self.out_edges.append(e)
        self.init_sender_socket(e.receiving_port, e)

    def add_in_edge(self, e):
        self.in_edges.append(e)
        threading.Thread(target=self.init_receiver_socket, args=(socket.gethostname(), e.receiving_port, e)).start()

    def update(self):
        for e in self.out_edges:
            self.send_data(Message(self.node_id, self.dist, e.weight), e)

    def __eq__(self, other):
        if self.node_id == other.nom:
            return True
        return False

    def __str__(self):
        return str(self.node_id)


def print_res(nodes):
    sleep(15)
    for n in nodes:
        print(n, nodes[n].dist, nodes[n].parent)


if __name__ == '__main__':
    line = input()  # nid1, nid2, edge_weight, edge_delay
    nodes = {}  # nid: Node
    i = 0
    while line:
        line = list(map(lambda x: int(x), line.split(' ')))  # nid1, nid2, edge_weight, edge_delay
        nid1, nid2, edge_weight, edge_delay = line
        e = Edge(edge_weight, edge_delay, BASE_PORT + i)
        if nid1 in nodes:  # Source node already exists
            n1 = nodes[nid1]
        else:  # New node
            n1 = Node(nid1)
            nodes[nid1] = n1
        if nid2 in nodes:  # Destination node already exists
            n2 = nodes[nid2]
        else:  # New node
            n2 = Node(nid2)
            nodes[nid2] = n2
        n2.add_in_edge(e)
        n1.add_out_edge(e)
        line = input()
        i += 1

    nodes[0].update()
    threading.Thread(target=print_res, args=(nodes,)).start()
