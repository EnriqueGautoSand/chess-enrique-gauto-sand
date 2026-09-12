import unittest
from app import app
from game_engine import GameEngine

class TestPvEMoves(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_pve_gameplay(self):
        res = self.client.post('/api/new_game', json={
            'color': 'white',
            'game_mode': 'pve',
            'depth': 2,
            'strategy': 'tactico'
        })
        data = res.get_json()
        self.assertTrue(data['success'])

        res = self.client.post('/api/move', json={
            'from': 'e2',
            'to': 'e4',
            'depth': 2,
            'strategy': 'tactico'
        })
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIsNotNone(data.get('ai_move'))
        
        ai_move = data['ai_move']
        self.assertTrue(ai_move['success'])
        print(f"Jugada del Humano: e2->e4 | Jugada de la IA: {ai_move['move_san']}")

        res_eval = self.client.get('/api/analyze?depth=2&strategy=tactico')
        eval_data = res_eval.get_json()
        self.assertIn('score', eval_data)
        self.assertIn('eval_white', eval_data)
        print(f"Evaluación resultante: eval_white={eval_data['eval_white']}, mate_in={eval_data.get('mate_in')}")

        state = data['state']
        history_len = len(state['history'])
        self.assertEqual(history_len, 2)

        res_dest = self.client.get('/api/legal_moves?square=g1')
        dests = res_dest.get_json()['destinations']
        self.assertTrue(len(dests) > 0)
        target_sq = dests[0]

        res2 = self.client.post('/api/move', json={
            'from': 'g1',
            'to': target_sq,
            'depth': 2,
            'strategy': 'tactico'
        })
        data2 = res2.get_json()
        self.assertTrue(data2['success'])
        print(f"Segundo movimiento del Humano: g1->{target_sq} | Respuesta de la IA: {data2.get('ai_move', {}).get('move_san')}")

    def test_truncate_and_branch_move(self):
        # Reiniciar partida
        self.client.post('/api/new_game', json={'color': 'white', 'game_mode': 'pve'})
        # 1. e4 (Humano) + respuesta IA (ej: 1... e5)
        self.client.post('/api/move', json={'from': 'e2', 'to': 'e4'})
        
        # Ahora el historial tiene 2 movimientos (0: e4, 1: respuesta IA).
        # El usuario retrocede a la posición inicial (-1) o tras 1. e4 (1) y decide cambiar su movimiento 1. d4 en lugar de 1. e4
        res = self.client.post('/api/move', json={
            'from': 'd2',
            'to': 'd4',
            'truncate_at': -1  # Ramificar desde la posición inicial
        })
        data = res.get_json()
        self.assertTrue(data['success'])
        history = data['state']['history']
        self.assertEqual(history[0]['san'], 'd4')
        self.assertIsNotNone(data.get('ai_move'))
        print(f"Ramificación exitosa desde el pasado: 1. d4 | IA responde: {data['ai_move']['move_san']}")

    def test_depth_5_performance(self):
        import time
        t0 = time.time()
        res = self.client.get('/api/analyze?depth=5&strategy=tactico')
        t1 = time.time()
        data = res.get_json()
        duration = t1 - t0
        print(f"Análisis Nivel 5 (Maestro) completado en {duration:.3f} segundos. Puntuación: {data.get('score')}")
        self.assertTrue(duration < 2.0, f"El análisis a Profundidad 5 tardó demasiado: {duration:.3f}s")

    def test_full_tree_with_time_limit(self):
        import time
        t0 = time.time()
        res = self.client.get('/api/analyze?depth=5&strategy=tactico&tree_mode=full&time_limit=1')
        t1 = time.time()
        duration = t1 - t0
        data = res.get_json()
        print(f"Análisis Árbol Completo con Límite 1s completado en {duration:.3f} segundos. Puntuación: {data.get('score')}")
        self.assertTrue(duration <= 1.8, f"El límite de tiempo no se respetó: {duration:.3f}s")

    def test_full_tree_depth_5_unlimited(self):
        import time
        t0 = time.time()
        res = self.client.get('/api/analyze?depth=5&strategy=tactico&tree_mode=full')
        t1 = time.time()
        duration = t1 - t0
        data = res.get_json()
        print(f"Análisis Árbol Completo (Nivel 5 Sin Límite) completado en {duration:.3f} segundos. Puntuación: {data.get('score')}")
        self.assertTrue(duration < 5.0, f"Árbol Completo a Nivel 5 tardó demasiado: {duration:.3f}s")

if __name__ == '__main__':
    unittest.main()
