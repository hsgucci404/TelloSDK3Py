#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ライブラリのインポート
from TelloSDK3 import Tello		# TelloSDK3.pyからTelloクラスをインポート
import time						# time.sleepを使いたいので
import cv2						# OpenCVを使うため

# メイン関数
def main():
	# (1) 初期化処理
	# Telloクラスを使って，telloというインスタンス(実体)を作る
	tello = Tello( )
	
	# Telloに接続する
	if tello.connect() == 'none_response':	# Telloの応答がなければ終了
		print('not connected to Tello.')
		return
	
	# 映像転送を有効にする
	tello.streamon()				# 映像のストリーミング開始
	
	time.sleep(1)		# 通信が安定するまでちょっと待つ
	
	# (2) ループ処理
	try:
		while True:	#Ctrl+cが押されるまでループ
			
			# (A)画像取得
			image = tello.read()	# 映像を1フレーム取得
			if image is None or image.size == 0:	# 中身がおかしかったら無視
				continue 
			
			# (B)画像サイズ/カメラ向きの変更
			small_image = cv2.resize(image, dsize=(480,360) )	# 画像サイズを半分に変更
			
			# (C)画像処理
			
			
			# (Y)ウィンドウ表示
			cv2.imshow('OpenCV Window', small_image)	# ウィンドウに表示するイメージを変えれば色々表示できる
			
			# (Z)キー入力
			key = cv2.waitKey(1) & 0xFF	# キー入力を1ms待つ
			if key == 27:					# k が27(ESC)だったらwhileループを脱出，プログラム終了
				break
			elif key == ord('t'):
				tello.takeoff()			# 離陸
			elif key == ord('g'):
				tello.throwfly()			# 離陸
			elif key == ord('l'):
				tello.land()				# 着陸
			elif key == ord('w'):
				tello.move_forward(30)	# 前進
			elif key == ord('s'):
				tello.move_backward(30)	# 後進
			elif key == ord('a'):
				tello.move_left(30)		# 左移動
			elif key == ord('d'):
				tello.move_right(30)	# 右移動
			elif key == ord('q'):
				tello.rotate_ccw(30)	# 左旋回
			elif key == ord('e'):
				tello.rotate_cw(30)		# 右旋回
			elif key == ord('r'):
				tello.move_up(30)		# 上昇
			elif key == ord('f'):
				tello.move_down(30)		# 下降
			elif key == ord('p'):
				print( tello.reboot() )

	except( KeyboardInterrupt, SystemExit):    # Ctrl+cを検知
		print( "SIGINTを検知" )
	
	# (3) 終了処理
	tello.land()		# 空中でESCキーやCtrl+cを押すかもしれないので
	time.sleep(2)		# 着陸待ち
	
	cv2.destroyAllWindows()	# OpenCVウィンドウの消去
	
	tello.streamoff()			# 映像ストリーミングを止めて熱暴走を防ぐ
	
	time.sleep(2)					# 映像関連の停止を待つ
	
	del tello						# telloクラスを削除
	# メイン関数終了

# "python main.py"として実行された時だけ動く様にするおまじない処理
if __name__ == "__main__":		# importされると"__main__"は入らないので，実行かimportかを判断できる．
	main()    # メイン関数を実行
