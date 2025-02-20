import unittest

from dao import *



class MyTestCase(unittest.TestCase):
    def test_UserDAO(self):
        userDAO = UserDAO()
        # res = userDAO.create_user("333", "Jack", 2, 180, 60, 21, "轻度运动")
        user = userDAO.get_user_by_wx_id("333")
        print(user)
        self.assertEqual(not user, False, "结果应该是 False")  # add assertion here


if __name__ == '__main__':
    unittest.main()
