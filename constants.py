# Split types supported         
SPLIT_TYPES = ['amount', 'equal', 'share'] 


# Maximum character length
EXP_DESCR_MAX_CHARS = 50

# Dictionary with different error types
ERROR_MASTER = {
    'descr' : {
        "message" : f"Expense description is longer than {EXP_DESCR_MAX_CHARS} characters" ,
        "element_type" : "expense(s)" } ,
    'date' : {
        "message" : "Review date format" ,
        "element_type" : "expense(s)" },
    'group_member' : {
        "message" : "Some member names do not match accross the two sheets" ,
        "element_type" : "column(s)" },
    'n_members' : {
        "message" : "Number of friends in file is different from members in the group" ,
        "element_type" : "general" },    
    'shares_no_addup' : {
        "message" : "Shares do not add up" ,
        "element_type" : "expense(s)" },
    'split_type_unsupported' : {
        "message" : "Split type is not supported, choose one of the following: " + ", ".join(["'" + t + "'" for t in SPLIT_TYPES]),
        "element_type" : "expense(s)" }
}