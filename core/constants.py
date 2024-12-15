# Split types supported         
SPLIT_TYPES = ['amount', 'equal', 'share'] 


# Maximum character length
EXP_DESCR_MAX_CHARS = 50

# Dictionary with different error types
ERROR_MASTER = {
    'group_member' : {
        "message" : "Some member names do not match accross the two sheets" ,
        "element_type" : "name(s)" },
    'n_members' : {
        "message" : "Number of friends in file is different from members in the group" ,
        "element_type" : "general" },    
    'descr' : {
        "message" : f"Expense description is longer than {EXP_DESCR_MAX_CHARS} characters" ,
        "element_type" : "expense(s)" } ,
    'date' : {
        "message" : "Review date format" ,
        "element_type" : "expense(s)" },
    'shares_no_addup' : {
        "message" : "Shares do not add up" ,
        "element_type" : "expense(s)" },
    'split_type_unsupported' : {
        "message" : "Split type is not supported, choose one of the following: " + ", ".join(["'" + t + "'" for t in SPLIT_TYPES]),
        "element_type" : "expense(s)" },
    'payer_name_error' : {
        "message" : 'Payer name does not match any of the members. Check the sheet "Members"',
        "element_type" : "expense(s)" }
}