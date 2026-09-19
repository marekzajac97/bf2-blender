
def console_command(func):
    func._console_callable = True
    return func
