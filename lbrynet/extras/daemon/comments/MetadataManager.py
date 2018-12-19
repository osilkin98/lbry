import logging

log = logging.getLogger(__name__)

'''
Very simple manager for handling comment interactions on a single 
page URI, made for demoing more than anything, but i like the model of it 
so i'll just drop it here for reference if i need to look back on something
which i likely wont but its still good to have

also a lot of the code written here i did when i was completely brain dead 
exhausted so dont beat me over the head if it's not up to my usual standard
because believe me, I know

class Content:
    comments = {}
    def __init__(self, uri, username=None, api=None, message_width=120):
        self.uri: str = uri
        self.api: CommentsAPI = CommentsAPI(username) if api is None else api
        self.width = message_width
        
    def comment(self, username, message):
        self.api.username = username
        comment_id = self.api.make_comment(self.uri, message)
        self.comments[comment_id] = self.api.get_comment(comment_id)
        
    def reply(self, comment_id, username, message):
        self.api.username = username
        reply_id = self.api.reply(comment_id, message)
        self.comments[reply_id] = self.api.get_comment(reply_id)
    
    def print_comment(self, comment, tab_depth=0):
        if comment.parent_index is None:
            print(f'[{comment.id}] {comment.author} said:')
        else:
            print('\t'*tab_depth + f'[{comment.id}] {comment.author} replied to {self.comments[comment.parent_index].author}:')
        message_fragged = comment.body.split()
        message_blocks, temp = [], ''
        for word in message_fragged:
            if self.width < len(word) + len(temp):
                message_blocks.append(temp)
                temp = ''
            temp += ' ' + word
        if len(temp) != 0:
            message_blocks.append(temp)
        for line in message_blocks:
            print('\t'*tab_depth + line)
        print()
    
    def print_thread(self, comment, tab_width=0):
        self.print_comment(comment, tab_width)
        comment_replies = self.api._get_comment_reply_id_list(comment.id)
        for reply in comment_replies:
            if reply not in self.comments:
                reply = self.api.get_comment(reply)
                self.comments[reply.id] = reply
            self.print_thread(reply, tab_width + 1)
    def print(self):
        tlc_list = self.api.get_claim_comments(self.uri)
        if tlc_list is not None:
            for comment in tlc_list:
                if comment.id not in self.comments:
                    self.comments[comment.id] = comment
                self.print_thread(comment)

'''