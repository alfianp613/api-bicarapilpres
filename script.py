from backend import *
import logging

logging.basicConfig(filename='/root/api-bicarapilpres/script.log', level=logging.DEBUG)

logging.info('Script started running at: %s' % datetime.now())



# Your script code here
main()

logging.info('Script finished running at: %s' % datetime.now())

