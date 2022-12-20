from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import User, ExpenseUser
from splitwise.group import Group


# class Group:
#     def __init__(self):
#         self.id = 0
#         self.name = ''
#         self.members = []
#     def add_member(self, new_member):
#         self.members.append(new_member)
#     def get_member_names(self):
#         "Return a list with member names"
#         member_list = [member.name for member in self.members]
#         return member_list
#     def get_member_ids(self):
#         member_list = [member.id for member in self.members]
#         return member_list
#     def get_member_dict(self):
#         member_dict = [{'id': member.id, 'name' : member.name} for member in self.members]
#         return member_dict

class Member:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class UpMember:
    """Members present in the upload file"""
    def __init__(self, orig_name = '', final_id : int = 0, final_name: str = '', candidates: list = [], correct : bool = False):
        self.orig_name = orig_name
        self.candidates = candidates
        self.final_id = final_id
        self.final_name = final_name
        self.correct = correct
    # def find_match_sw(self, group: Group):
    #     """ Find matching """
    #     for member in group.getMembers():
    #         member_full_name = member.getFirstName() + " " + member.getLastName()
    #         if self.orig_name == member_full_name
    #         User.fried
    #         Splitwise.user.Friend.
    
    def add_candidate(self, candidate_id : int, candidate_name : str):
        if not (isinstance(candidate_id, int)): TypeError("Candidate ID must be int")
        if not (isinstance(candidate_name, str)): TypeError("Candidate name must be str")
        self.candidates.append({'id' : candidate_id, 'name' : candidate_name})

class UpExpense:
    def __init__(self):
        self.id : int
        self.description : str
        self.date : str
        self.amount : float
        self.currency : str
        self.payer_id : int
        self.all_equal : bool
        self.type_split : str
        self.exp_members = [] # Must be composed of Up_members
    def add_member(self, new_member : UpMember):
        """ Add an UpMember to the expense"""
        self.exp_members.append(new_member)
    def sw_class(self):
        """Take an UpExpense object and return a Splitwise Expense object from """
        expense = Expense()
        expense.setCost(self.amount)
        expense.setDescription(self.description)
        expense.setDate(self.date)
        expense.setCurrencyCode(self.currency)
        return expense


