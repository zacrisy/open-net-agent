.PHONY: test test-wss run demo
test:
	python3 -m py_compile coordinator.py coordinator_async.py node.py node_async.py skills.py db.py db_async.py sandbox.py
	python3 test_plugin_integrity.py
	python3 test_bandit.py
	python3 test_system.py
	python3 test_sandbox.py

test-wss:
	openssl req -x509 -newkey rsa:2048 -keyout /tmp/wss-key.pem -out /tmp/wss-cert.pem -days 1 -nodes -subj "/CN=localhost" 2>/dev/null
	python3 test_wss.py

run:
	python3 run_online.py

demo:
	python3 demo.py
