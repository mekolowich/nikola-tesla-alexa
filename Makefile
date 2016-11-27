
status:
	eb status

local:
	./application.py

deploy:
	eb deploy
	eb status

init:
	eb init
