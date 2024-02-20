from copy import deepcopy
from . import move_detector as md, move_selector as ms
from .move_generator import MovesGener
import random
from search_utility import search_actions, select_optimal_path, check_42
from .move_detector import get_move_type

EnvCard2RealCard = {3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
                    8: '8', 9: '9', 10: 'T', 11: 'J', 12: 'Q',
                    13: 'K', 14: 'A', 17: '2', 20: 'X', 30: 'D'}

RealCard2EnvCard = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
                    '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12,
                    'K': 13, 'A': 14, '2': 17, 'X': 20, 'D': 30}

AllEnvCard = [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7,
              8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 11, 12,
              12, 12, 12, 13, 13, 13, 13, 14, 14, 14, 14, 17, 17, 17, 17, 20, 30]

bombs = [[3, 3, 3, 3], [4, 4, 4, 4], [5, 5, 5, 5], [6, 6, 6, 6],
         [7, 7, 7, 7], [8, 8, 8, 8], [9, 9, 9, 9], [10, 10, 10, 10],
         [11, 11, 11, 11], [12, 12, 12, 12], [13, 13, 13, 13], [14, 14, 14, 14],
         [17, 17, 17, 17], [20, 30]]


class GameEnv(object):

    def __init__(self, players, players2=None):

        self.game_infoset = None
        self.card_play_action_seq = []

        self.three_landlord_cards = None
        self.game_over = False

        self.acting_player_position = None
        self.player_utility_dict = None

        self.players = players
        self.players2 = players2
        self.model_type = ""

        self.last_move_dict = {'landlord': [],
                               'landlord_up': [],
                               'landlord_down': []}

        self.played_cards = {'landlord': [],
                             'landlord_up': [],
                             'landlord_down': []}

        self.last_move = []
        self.last_two_moves = []

        self.num_wins = {'landlord': 0,
                         'farmer': 0}

        self.num_scores = {'landlord': 0,
                           'farmer': 0}

        self.info_sets = {'landlord': InfoSet('landlord'),
                          'landlord_up': InfoSet('landlord_up'),
                          'landlord_down': InfoSet('landlord_down')}

        self.bomb_num = 0
        self.last_pid = 'landlord'

        self.bid_info = [[1, 0.5, 1],
                         [1, 1, 1],
                         [1, 1, -4],
                         [1, 1, 1]]

        self.multiply_info = [1, 1, 1]
        self.bid_count = 0
        self.multiply_count = {'landlord': 1,
                               'landlord_up': 1,
                               'landlord_down': 1}
        self.step_count = 0

    def card_play_init(self, card_play_data):
        self.info_sets['landlord'].player_hand_cards = \
            card_play_data['landlord']
        self.info_sets['landlord_up'].player_hand_cards = \
            card_play_data['landlord_up']
        self.info_sets['landlord_down'].player_hand_cards = \
            card_play_data['landlord_down']
        self.three_landlord_cards = card_play_data['three_landlord_cards']
        self.get_acting_player_position()
        self.game_infoset = self.get_infoset()

    def game_done(self):
        if len(self.info_sets['landlord'].player_hand_cards) == 0 or \
                len(self.info_sets['landlord_up'].player_hand_cards) == 0 or \
                len(self.info_sets['landlord_down'].player_hand_cards) == 0:
            # if one of the three players discards his hand,
            # then game is over.
            self.compute_player_utility()
            self.update_num_wins_scores()

            self.game_over = True

    def compute_player_utility(self):

        if len(self.info_sets['landlord'].player_hand_cards) == 0:
            self.player_utility_dict = {'landlord': 2,
                                        'farmer': -1}
        else:
            self.player_utility_dict = {'landlord': -2,
                                        'farmer': 1}

    def update_num_wins_scores(self):
        for pos, utility in self.player_utility_dict.items():
            base_score = 2 if pos == 'landlord' else 1
            if utility > 0:
                self.num_wins[pos] += 1
                self.winner = pos
                self.num_scores[pos] += base_score * (2 ** self.bomb_num)
            else:
                self.num_scores[pos] -= base_score * (2 ** self.bomb_num)

    def get_winner(self):
        return self.winner

    def get_bomb_num(self):
        return self.bomb_num

    def compare_action(self, action):
        return action[1]

    @staticmethod
    def action_to_str(action):
        if len(action) == 0:
            return "Pass"
        else:
            return "".join([EnvCard2RealCard[card] for card in action])

    def path_to_str(self, path):
        pstr = ""
        for action in path:
            pstr += self.action_to_str(action) + " "
        return pstr

    @staticmethod
    def have_bomb(cards):
        if 20 in cards and 30 in cards:
            return True
        for i in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17]:
            if cards.count(i) == 4:
                return True
        return False

    def step(self, position, action=None, update=True):  # 是否更新 info set
        if action is None:
            action = []
            win_rate = 0
            action_list = []
            if self.acting_player_position == position:
                if self.players2 is None:
                    action, actions_confidence, action_list = self.players[1].act(self.game_infoset)
                else:
                    action, actions_confidence, action_list = self.players2[1].act(self.game_infoset)
                win_rate = actions_confidence

                if len(action_list) >= 2:
                    # 地主胜率低于-0.2 不允许炸
                    if (((action in bombs) or (30 in action and 20 in action)) and position == "landlord"
                            and round(float(action_list[0][1]) * 8, 4) < -0.6):
                        action_list.sort(key=self.compare_action, reverse=True)
                        action, actions_confidence = action_list[1][0], action_list[1][1]
                        win_rate = actions_confidence

                    # 农民胜率低于 -0.2 不允许炸
                    if (((action in bombs) or (30 in action and 20 in action))
                            and position in ["landlord_up", "landlord_down"]
                            and round(float(action_list[0][1]) * 8, 4) < -0.6):
                        action_list.sort(key=self.compare_action, reverse=True)
                        action, actions_confidence = action_list[1][0], action_list[1][1]
                        win_rate = actions_confidence

                    # 当第一选择是pass，第二选择是炸弹，炸弹胜率大于0.6就可以炸了
                    if (action == [] and position == "landlord" and round(float(action_list[0][1]) * 8, 4) > 0.6
                            and action_list[1][0] in bombs):
                        action_list.sort(key=self.compare_action, reverse=True)
                        action, actions_confidence = action_list[1][0], action_list[1][1]
                        win_rate = actions_confidence

                    # 当胜率大于0.5  要是pass的话就选择第二手牌
                    if action == [] and round(float(action_list[0][1]) * 8, 4) > 0.5:
                        action_list.sort(key=self.compare_action, reverse=True)
                        action, actions_confidence = action_list[1][0], action_list[1][1]
                        win_rate = actions_confidence

                    # 相差小于0.05时，选第二个action
                    if (abs(round(float(action_list[0][1]) * 8, 4) - round(float(action_list[1][1]) * 8, 4)) < 0.005
                            and round(float(action_list[0][1]) * 8, 4) > 0.8 and action_list[0][1] == ""):
                        print("选择更稳的第二种出法")
                        action_list.sort(key=self.compare_action, reverse=True)
                        action, actions_confidence = action_list[1][0], action_list[1][1]
                        win_rate = actions_confidence

                # 对直接出完情况做特判
                print("正在检测可直接出完出法")
                print()
                if len(action) != len(self.game_infoset.player_hand_cards):
                    for l_action, l_score in action_list:
                        if len(l_action) == len(self.game_infoset.player_hand_cards):
                            m_type = md.get_move_type(l_action)
                            if m_type["type"] not in [md.TYPE_14_4_22, md.TYPE_13_4_2]:
                                action = l_action
                                win_rate = 10000
                                print("检测到可直接出完出法")
                    last_two_moves = self.get_last_two_moves()
                    rival_move = None
                    if last_two_moves[0]:
                        rival_move = last_two_moves[0]
                    elif last_two_moves[1]:
                        rival_move = last_two_moves[1]
                    if win_rate != 10000:
                        path_list = []
                        search_actions(self.game_infoset.player_hand_cards, self.game_infoset.other_hand_cards,
                                       path_list,
                                       rival_move=rival_move)
                        if len(path_list) > 0:
                            path = select_optimal_path(path_list)
                            if not check_42(path):
                                if action != path[0]:
                                    print("检测到可直接出完路径:", self.action_to_str(action), "->",
                                          self.path_to_str(path))
                                    action = path[0]
                                    win_rate = 20000
        else:
            action_list = [[action, 0]]
            win_rate = 0

        if update:
            if len(action) > 0:
                self.last_pid = self.acting_player_position

            if action in bombs:
                self.bomb_num += 1

            self.last_move_dict[
                self.acting_player_position] = action.copy()

            self.card_play_action_seq.append((position, action))
            self.update_acting_player_hand_cards(action)

            self.played_cards[self.acting_player_position] += action

            if self.acting_player_position == 'landlord' and \
                    len(action) > 0 and \
                    len(self.three_landlord_cards) > 0:
                for card in action:
                    if len(self.three_landlord_cards) > 0:
                        if card in self.three_landlord_cards:
                            self.three_landlord_cards.remove(card)
                    else:
                        break
            self.game_done()
            if not self.game_over:
                self.get_acting_player_position()
                self.game_infoset = self.get_infoset()

        # 返回动作和胜率,只有玩家角色会接受返回值
        action_message = {"action": str(''.join([EnvCard2RealCard[c] for c in action])),
                          "win_rate": float(win_rate) * 8}
        action_list.sort(key=self.compare_action, reverse=True)
        show_action_list = [(str(''.join([EnvCard2RealCard[c] for c in action_info[0]])) if len(
            str(''.join([EnvCard2RealCard[c] for c in action_info[0]]))) > 0 else "Pass",
                             str(round(float(action_info[1]) * 8, 4))) for action_info in action_list]
        return action_message, show_action_list

    def get_last_move(self):
        last_move = []
        if len(self.card_play_action_seq) != 0:
            if len(self.card_play_action_seq[-1][1]) == 0:
                last_move = self.card_play_action_seq[-2][1]
            else:
                last_move = self.card_play_action_seq[-1][1]

        return last_move

    def get_last_two_moves(self):
        last_two_moves = [[], []]
        for card in self.card_play_action_seq[-2:]:
            last_two_moves.insert(0, card[1])
            last_two_moves = last_two_moves[:2]
        return last_two_moves

    def get_acting_player_position(self):
        if self.acting_player_position is None:
            self.acting_player_position = 'landlord'

        else:
            if self.acting_player_position == 'landlord':
                self.acting_player_position = 'landlord_down'

            elif self.acting_player_position == 'landlord_down':
                self.acting_player_position = 'landlord_up'

            else:
                self.acting_player_position = 'landlord'

        return self.acting_player_position

    def update_acting_player_hand_cards(self, action):
        if action != []:
            # 更新玩家手牌，删除对应的牌
            if self.acting_player_position == self.players[0]:
                for card in action:
                    self.info_sets[self.acting_player_position].player_hand_cards.remove(card)
            # 更新另外两个玩家手牌，删除相同数量的牌
            else:
                del self.info_sets[self.acting_player_position].player_hand_cards[0:len(action)]
            self.info_sets[self.acting_player_position].player_hand_cards.sort()

    def get_legal_card_play_actions(self):
        mg = MovesGener(
            self.info_sets[self.acting_player_position].player_hand_cards)

        action_sequence = self.card_play_action_seq

        rival_move = []
        if len(action_sequence) != 0:
            if len(action_sequence[-1][1]) == 0:
                rival_move = action_sequence[-2][1]
            else:
                rival_move = action_sequence[-1][1]

        rival_type = md.get_move_type(rival_move)
        rival_move_type = rival_type['type']
        rival_move_len = rival_type.get('len', 1)
        moves = list()

        if rival_move_type == md.TYPE_0_PASS:
            moves = mg.gen_moves()

        elif rival_move_type == md.TYPE_1_SINGLE:
            all_moves = mg.gen_type_1_single()
            moves = ms.filter_type_1_single(all_moves, rival_move)

        elif rival_move_type == md.TYPE_2_PAIR:
            all_moves = mg.gen_type_2_pair()
            moves = ms.filter_type_2_pair(all_moves, rival_move)

        elif rival_move_type == md.TYPE_3_TRIPLE:
            all_moves = mg.gen_type_3_triple()
            moves = ms.filter_type_3_triple(all_moves, rival_move)

        elif rival_move_type == md.TYPE_4_BOMB:
            all_moves = mg.gen_type_4_bomb() + mg.gen_type_5_king_bomb()
            moves = ms.filter_type_4_bomb(all_moves, rival_move)

        elif rival_move_type == md.TYPE_5_KING_BOMB:
            moves = []

        elif rival_move_type == md.TYPE_6_3_1:
            all_moves = mg.gen_type_6_3_1()
            moves = ms.filter_type_6_3_1(all_moves, rival_move)

        elif rival_move_type == md.TYPE_7_3_2:
            all_moves = mg.gen_type_7_3_2()
            moves = ms.filter_type_7_3_2(all_moves, rival_move)

        elif rival_move_type == md.TYPE_8_SERIAL_SINGLE:
            all_moves = mg.gen_type_8_serial_single(repeat_num=rival_move_len)
            moves = ms.filter_type_8_serial_single(all_moves, rival_move)

        elif rival_move_type == md.TYPE_9_SERIAL_PAIR:
            all_moves = mg.gen_type_9_serial_pair(repeat_num=rival_move_len)
            moves = ms.filter_type_9_serial_pair(all_moves, rival_move)

        elif rival_move_type == md.TYPE_10_SERIAL_TRIPLE:
            all_moves = mg.gen_type_10_serial_triple(repeat_num=rival_move_len)
            moves = ms.filter_type_10_serial_triple(all_moves, rival_move)

        elif rival_move_type == md.TYPE_11_SERIAL_3_1:
            all_moves = mg.gen_type_11_serial_3_1(repeat_num=rival_move_len)
            moves = ms.filter_type_11_serial_3_1(all_moves, rival_move)

        elif rival_move_type == md.TYPE_12_SERIAL_3_2:
            all_moves = mg.gen_type_12_serial_3_2(repeat_num=rival_move_len)
            moves = ms.filter_type_12_serial_3_2(all_moves, rival_move)

        elif rival_move_type == md.TYPE_13_4_2:
            all_moves = mg.gen_type_13_4_2()
            moves = ms.filter_type_13_4_2(all_moves, rival_move)

        elif rival_move_type == md.TYPE_14_4_22:
            all_moves = mg.gen_type_14_4_22()
            moves = ms.filter_type_14_4_22(all_moves, rival_move)

        if rival_move_type not in [md.TYPE_0_PASS,
                                   md.TYPE_4_BOMB, md.TYPE_5_KING_BOMB]:
            moves = moves + mg.gen_type_4_bomb() + mg.gen_type_5_king_bomb()

        if len(rival_move) != 0:  # rival_move is not 'pass'
            moves = moves + [[]]

        for m in moves:
            m.sort()

        return moves

    def reset(self):
        self.card_play_action_seq = []

        self.three_landlord_cards = None
        self.game_over = False

        self.acting_player_position = None
        self.player_utility_dict = None

        self.last_move_dict = {'landlord': [],
                               'landlord_up': [],
                               'landlord_down': []}

        self.played_cards = {'landlord': [],
                             'landlord_up': [],
                             'landlord_down': []}

        self.last_move = []
        self.last_two_moves = []

        self.info_sets = {'landlord': InfoSet('landlord'),
                          'landlord_up': InfoSet('landlord_up'),
                          'landlord_down': InfoSet('landlord_down')}

        self.bomb_num = 0
        self.last_pid = 'landlord'
        self.bid_info = [[1, 0.5, 1],
                         [1, 1, 1],
                         [1, 1, -4],
                         [1, 1, 1]]

        self.multiply_info = [1, 1, 1]
        self.bid_count = 0
        self.multiply_count = {'landlord': 0,
                               'landlord_up': 0,
                               'landlord_down': 0}
        self.step_count = 0

    def get_infoset(self):
        self.info_sets[
            self.acting_player_position].last_pid = self.last_pid

        self.info_sets[
            self.acting_player_position].legal_actions = \
            self.get_legal_card_play_actions()

        self.info_sets[
            self.acting_player_position].bomb_num = self.bomb_num

        self.info_sets[
            self.acting_player_position].last_move = self.get_last_move()

        self.info_sets[
            self.acting_player_position].last_two_moves = self.get_last_two_moves()

        self.info_sets[
            self.acting_player_position].last_move_dict = self.last_move_dict

        self.info_sets[self.acting_player_position].num_cards_left_dict = \
            {pos: len(self.info_sets[pos].player_hand_cards)
             for pos in ['landlord', 'landlord_up', 'landlord_down']}

        self.info_sets[self.acting_player_position].other_hand_cards = []

        '''
        调整计算其他人手牌的方法，整副牌减去玩家手牌与出过的牌
        for pos in ['landlord', 'landlord_up', 'landlord_down']:
            if pos != self.acting_player_position:
                self.info_sets[
                    self.acting_player_position].other_hand_cards += \
                    self.info_sets[pos].player_hand_cards
        '''
        # 把出过的牌中三个子列表合成一个列表
        played_cards_tmp = []
        for i in list(self.played_cards.values()):
            played_cards_tmp.extend(i)
        # 出过的牌和玩家手上的牌
        played_and_hand_cards = played_cards_tmp + self.info_sets[self.acting_player_position].player_hand_cards
        # 整副牌减去出过的牌和玩家手上的牌，就是其他人的手牌
        for i in set(AllEnvCard):
            self.info_sets[
                self.acting_player_position].other_hand_cards.extend(
                [i] * (AllEnvCard.count(i) - played_and_hand_cards.count(i)))

        self.info_sets[self.acting_player_position].played_cards = \
            self.played_cards
        self.info_sets[self.acting_player_position].three_landlord_cards = \
            self.three_landlord_cards
        self.info_sets[self.acting_player_position].card_play_action_seq = \
            self.card_play_action_seq

        self.info_sets[
            self.acting_player_position].all_handcards = \
            {pos: self.info_sets[pos].player_hand_cards
             for pos in ['landlord', 'landlord_up', 'landlord_down']}

        return deepcopy(self.info_sets[self.acting_player_position])


class InfoSet(object):
    """
    The game state is described as infoset, which
    includes all the information in the current situation,
    such as the hand cards of the three players, the
    historical moves, etc.
    """

    def __init__(self, player_position):
        # The player position, i.e., landlord, landlord_down, or landlord_up
        self.player_position = player_position
        # The hand cands of the current player. A list.
        self.player_hand_cards = None
        # The number of cards left for each player. It is a dict with str-->int
        self.num_cards_left_dict = None
        # The three landload cards. A list.
        self.three_landlord_cards = None
        # The historical moves. It is a list of list
        self.card_play_action_seq = None
        # The union of the hand cards of the other two players for the current player
        self.other_hand_cards = None
        # The legal actions for the current move. It is a list of list
        self.legal_actions = None
        # The most recent valid move
        self.last_move = None
        # The most recent two moves
        self.last_two_moves = None
        # The last moves for all the postions
        self.last_move_dict = None
        # The played cands so far. It is a list.
        self.played_cards = None
        # The hand cards of all the players. It is a dict.
        self.all_handcards = None
        # Last player position that plays a valid move, i.e., not `pass`
        self.last_pid = None
        # The number of bombs played so far
        self.bomb_num = None

        self.bid_info = [[1, 0.5, 1],
                         [1, 1, 1],
                         [1, 5, -4],
                         [1, 1, 1]]
        if player_position == 'landlord_up':
            self.bid_info = [[1, 0.2, 1],
                             [1, 3.5, 1],
                             [1, 5, 4],
                             [1.035, 1, 0.15]]
        if player_position == 'landlord_down':
            self.bid_info = [[1, 0.2, 1],
                             [1, 3.5, 1],
                             [1, 5, 4],
                             [1.035, 1, 0.15]]

        self.multiply_info = [1, 0.8, 1.3]
        # self.multiply_info = [1, 1, 1]
        # self.multiply_info = [0, 0, 0]
        if player_position == 'landlord_up':
            self.multiply_info = [1, 2.5, 1.3]
        if player_position == 'landlord_down':
            self.multiply_info = [1, 2.5, 1.3]
        self.player_id = None
