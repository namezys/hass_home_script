
class HomeObject:
    """
    Helper to define object.

    Iy will help during debuging and loging
    """

    def __str__(self):
        return type(self).__qualname__
