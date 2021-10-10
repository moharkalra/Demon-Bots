import cv2
import serial, struct
import numpy as np
import pic2oled as p
from time import sleep
from PIL import Image, ImageDraw, ImageFont
from matplotlib import cm
from socket import *
from re import *
import sys
import select
import os
import time
import threading

def process(clientSocket):
    #processes messages from clients and returns responses to clientSocket
    #passes in the client socket connected to the proxy

    #continuously running loop
    while True:
        try:
            #if a message is received and it is not empty
            message = clientSocket.recv(1024).decode()
            if message:
                print("Message from client: ", message)
                #server name, filepath and http version are extracted from client request
                domain = message.split('/')
                domain = domain[1]
                url = domain.upper()
                print("DOMAIN: " + domain)
                sendImage(url)


                clientSocket.close()

                print(" Client Connection closed")
            else:
                readable, writable, errorable = select([],[], [clientSocket])
                for s in errorable:
                    s.close()
                break
        except:
            #if the message has no content, connection to client is closed
            clientSocket.close()

            print("Client Connection closed")
            break



def main():
    serverPort = 80

     # creates socket to listen for client requests
    listeningPort = 8081
    listeningAddr = ''  # localhost
    listeningSocket = socket(AF_INET, SOCK_STREAM)

    # Bind socket and listen to incoming connections
    listeningSocket.bind((listeningAddr, listeningPort))
    listeningSocket.listen(5)
    print('Listening on:', listeningPort);

    while True:
        # Accept incoming connections
        clientSocket, clientAddr = listeningSocket.accept() # returns tuple
        print("Connected to client on ", clientAddr)
        #creates a thread to handle the client request while allowing the main thread to still receive other client requests
        process(clientSocket)

    listeningSocket.close()
if __name__ == "__main__":
    main()
