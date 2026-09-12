import unittest
import chess
from app import app
from game_engine import GameEngine

class TestChessUIIntegration(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.game = GameEngine()

    def test_new_game_pvp(self):
        response = self.client.post('/api/new_game', json={
            'color': 'white',
            'game_mode': 'pvp',
            'depth': 2,
            'strategy': 'tactico'
        })
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['state']['game_mode'], 'pvp')

    def test_live_analysis(self):
        response = self.client.get('/api/analyze?depth=2&strategy=tactico')
        data = response.get_json()
        self.assertIn('title', data)
        self.assertIn('explanation', data)
        self.assertIn('eval_white', data)
        self.assertIn('turn', data)
        self.assertEqual(data['turn'], 'white')
        self.assertIsInstance(data['eval_white'], float)

    def test_load_pgn_endpoint(self):
        pgn_sample = "1. e4 d5 2. exd5 Qxd5 3. Nc3 Qd7"
        response = self.client.post('/api/load_pgn', json={
            'pgn': pgn_sample,
            'depth': 2,
            'strategy': 'tactico'
        })
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['parsed_moves'], 6)
        self.assertEqual(len(data['state']['history']), 6)

    def test_find_forced_mate(self):
        # Jaque mate en 1 (Fool's Mate)
        board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2")
        # Negras juegan Qh4#
        mate_n = self.game.find_forced_mate(board, max_depth=3)
        self.assertEqual(mate_n, 1)

if __name__ == '__main__':
    unittest.main()
