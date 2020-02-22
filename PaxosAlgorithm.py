import socket
import threading
from time import sleep
from icecream import ic
import json

BASE_PORT = 53120
STATUS = ['SLEEP', 'SELF_LEADER', 'HAS_LEADER', 'NO_LEADER']
MESSAGE_TYPE = ['POTENTIAL_LEADER', 'V_PROPOSE', 'V_DECIDE', 'POTENTIAL_LEADER_ACK', 'V_PROPOSE_ACK']
PHASE = ['P1', 'P2', 'P3']
SIZE_OF_NETWORK = 5
DEFAULT_V = 4


class Message:
    def __init__(self, nid, m_type, m_value):
        self.nid = nid  # nid of sender
        self.m_type = m_type  # Type of message, one of MESSAGE_TYPEs
        self.m_value = m_value  # Value of message

    def __str__(self):
        return '{} {} {}'.format(self.nid, self.m_type, self.m_value)


class Node:
    def __init__(self, nid, t1, t2, t3):
        self.nid = nid  # Node ID
        self.t1 = t1  # Timeout for waking up and advertising for itself as a potential leader
        self.t2 = t2  # Timeout for waiting to collect all responses and become a leader
        self.t3 = t3  # Timeout for waiting to collect all accepts and deciding for V
        self.status = STATUS[0]  # First it is set to SLEEP
        self.max_id_seen = 0  # Set it to 0 first
        self.port_delay_table = {}
        # For node 0:
        # { 1: (54321, delay),
        #   2: (54322, delay),
        #   3: (54323, delay),
        #   4: (54324, delay) }
        self.sending_sockets = {}
        # For node 0:
        # { 1: socket,
        #   2: socket,
        # ...}
        self.last_sent_pl_id = -1
        self.receiving_ports = []  # List of receiving ports, used for receiving
        self.v_id_pairs = {}
        self.max_sending_delay = 0  # Maximum send delay, DON'T USE FOR NOW
        self.phase = None
        self.received_acknowledgements = 0  # number of received acknowledgements (response of other nodes)
        self.chosen_v = DEFAULT_V * self.nid  # Could be used for both last seen v (not leader) and decided v (leader actually)
        self.timeout_valid = False  # When received_acks passes (nesf+1) check if time is out
        self.terminate = False

    def init_sending_sockets(self):
        for nid in self.port_delay_table:
            sock = socket.socket()
            sock.connect(('localhost', self.port_delay_table[nid][0]))
            self.sending_sockets[nid] = sock

    def init_receiver_sockets(self):
        for port in self.receiving_ports:
            threading.Thread(target=self._init_receiver_socket, args=('localhost', port)).start()

    def _init_receiver_socket(self, host, port):
        receiver_socket = socket.socket()
        receiver_socket.bind((host, port))
        receiver_socket.listen()
        sender_connection_socket, address = receiver_socket.accept()

        while True:
            # print("node " + str(self.nid) + " ready to recv")
            data = sender_connection_socket.recv(1024).decode()
            if not data:
                break
            m = Message(**json.loads(data, encoding='utf-8'))
            print('in node {} received'.format(self.nid), m)

            if m.m_type == MESSAGE_TYPE[0]:  # Potential Leader
                if (self.max_id_seen != 0) and (int(m.m_value) <= self.max_id_seen):
                    continue

                # if self.nid == 1:
                #     print(self.status, (self.max_id_seen + 1), int(m.m_value))
                if (self.phase is not None) and ((self.max_id_seen + 1) < int(m.m_value)):
                    ic()
                    self.status = STATUS[0]
                    self.phase = None
                    self.timeout_valid = False
                    # print("timeout invalid 85", self.nid)
                    self.received_acknowledgements = 0
                    # continue #:-?

                if self.max_id_seen < int(m.m_value):
                    self.max_id_seen = int(m.m_value)

                if len(self.v_id_pairs) == 0:
                    message_to_send = Message(self.nid, MESSAGE_TYPE[3], -1)
                else:
                    message_to_send = Message(self.nid, MESSAGE_TYPE[3], self.v_id_pairs[
                        max(self.v_id_pairs.keys())])
                self.send_message(m.nid, message_to_send, self.port_delay_table[m.nid][1])
            elif m.m_type == MESSAGE_TYPE[1]:  # V_PROPOSE
                if int(m.m_value.split(',')[0]) != self.max_id_seen:
                    continue
                if ',' not in m.m_value or int(m.m_value.split(',')[0]) != self.max_id_seen:  # Value: id,value
                    continue

                self.v_id_pairs[int(m.m_value.split(',')[0])] = m.m_value.split(',')[1]
                message_to_send = Message(self.nid, MESSAGE_TYPE[4], -1)
                self.send_message(m.nid, message_to_send, self.port_delay_table[m.nid][1])
            elif m.m_type == MESSAGE_TYPE[2]:  # V_DECIDE
                self.terminate = True
                break

            elif m.m_type == MESSAGE_TYPE[3]:  # POTENTIAL_LEADER_ACK
                if self.timeout_valid:
                    self.received_acknowledgements += 1
                    if self.received_acknowledgements > int(SIZE_OF_NETWORK / 2):
                        self.status = STATUS[1]
                        self.received_acknowledgements = 0
                        threading.Thread(target=self.p3_cycle).start()
                else:
                    # timeout shod
                    pass
            elif m.m_type == MESSAGE_TYPE[4]:  # V_PROPOSE_ACK
                # print("117,", self.status, self.timeout_valid)
                if self.status == STATUS[1] and self.timeout_valid:
                    self.received_acknowledgements += 1
                    if self.received_acknowledgements > int(SIZE_OF_NETWORK / 2):
                        self.received_acknowledgements = 0
                        self.phase = PHASE[2]
                        self.decision_made()
                        # break
            else:
                continue

    def p1_p2_cycle(self):
        while True:
            if self.terminate:
                break
            # print("node", str(self.nid), "p1_p2_cycle started")
            if self.phase is not None:
                continue
            sleep(self.t1)
            # TODO: Check if it has another leader or not???
            self.last_sent_pl_id = self.max_id_seen + 1
            self.send_to_all_neighbours(Message(self.nid, MESSAGE_TYPE[0], self.max_id_seen + 1))
            # TODO: start t2 timeout after sending the last message
            # One possible solution: sleep(max(sending delays + Epsilon))
            self.t2_countdown()

    def decision_made(self):
        self.send_to_all_neighbours(Message(self.nid, MESSAGE_TYPE[2], self.chosen_v))
        self.terminate = True

    def p3_cycle(self):
        self.chosen_v = self.choose_v()
        self.send_to_all_neighbours(
            Message(self.nid, MESSAGE_TYPE[1], '{},{}'.format(self.last_sent_pl_id, self.chosen_v)))
        self.t3_countdown()
        # self.received_acknowledgements = 0

    def choose_v(self):
        return self.v_id_pairs[max(self.v_id_pairs.keys())] if len(self.v_id_pairs) != 0 else self.chosen_v

    # TODO: could be merged with t3 countdown :-?
    def t2_countdown(self):
        self.timeout_valid = True
        self.phase = PHASE[0]
        sleep(self.t2)
        if self.phase == PHASE[1]:
            return
        self.received_acknowledgements = 0
        self.timeout_valid = False
        # print("timeout invalid 160", self.nid)
        self.phase = None
        # One possible solution: sleep(self.t2)

    def t3_countdown(self):
        self.timeout_valid = True
        self.phase = PHASE[1]
        sleep(self.t3)

        self.phase = None
        self.received_acknowledgements = 0
        self.timeout_valid = False
        # print("timeout invalid 172", self.nid)
        # One possible solution: sleep(self.t2)

    def send_message(self, nid, message, delay):  # nid of target
        threading.Thread(target=self._send_message, args=(nid, message, delay)).start()

    def _send_message(self, nid, message, delay):  # nid of target
        # print(delay)
        sleep(delay)
        self.sending_sockets[nid].sendall(json.dumps(message.__dict__).encode('utf-8'))

    def send_to_all_neighbours(self, message):
        if self.terminate:
            return
        for nid in self.port_delay_table.keys():
            # if self.phase is not None:
            # print(self.nid, message.m_type, self.status)
            if message.m_type == MESSAGE_TYPE[1] and self.status == STATUS[0]:
                break
            self.send_message(nid, message, self.port_delay_table[nid][1])


if __name__ == '__main__':
    SIZE_OF_NETWORK = int(input())
    nodes = []
    base_port = BASE_PORT
    for i in range(SIZE_OF_NETWORK):
        nid_timeouts = input().split(' ')
        # print("timeout", nid_timeouts)
        nodes.append(Node(int(nid_timeouts[0]), int(nid_timeouts[1]), int(nid_timeouts[2]), int(nid_timeouts[3])))
        for j in range(SIZE_OF_NETWORK - 1):
            edge = input().split(' ')
            # print("edge", edge)
            nodes[i].port_delay_table[int(edge[0])] = (BASE_PORT + i * SIZE_OF_NETWORK + j, float(edge[1]))
            # print(i, nodes[i].port_delay_table, nodes[i].receiving_ports)
            # nodes[i].receiving_ports.append(BASE_PORT + i*SIZE_OF_NETWORK + j)
    for i in range(SIZE_OF_NETWORK):
        for j in range(SIZE_OF_NETWORK):
            if i == j:
                continue
            nodes[i].receiving_ports.append(nodes[j].port_delay_table[i + 1][0])
        # print(i+1, nodes[i].port_delay_table, nodes[i].receiving_ports)
        nodes[i].init_receiver_sockets()
    for node in nodes:
        node.init_sending_sockets()
    for node in nodes:
        threading.Thread(target=node.p1_p2_cycle).start()
#
# <size of network>
# <nid> <t1> <t2> <t3>
# <nid1> <delay>
# <nid2> <delay>
# ...
