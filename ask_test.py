from handlers.advanced_ask_handler import register_ask_handler

class B:
    def message_handler(self, **kwargs):
        def wrap(fn):
            self.fn = fn
            print("REGISTERED", fn.__name__)
            return fn
        return wrap

    def reply_to(self,msg,text,**kwargs):
        print("REPLY:",repr(text))

b=B()

print("BEFORE REGISTER")
register_ask_handler(b)
print("AFTER REGISTER")

class U:
    id=8789977826
    is_bot=False

class M:
    from_user=U()
    text="/ask test"

print("BEFORE CALL")
b.fn(M())
print("AFTER CALL")

