# --- LINKED LIST & QUEUE IMPLEMENTATION ---
class TrainNode:
    def __init__(self, train_id=None, next=None):
        self.train_id = train_id
        self.next = next
    
    def set_next(self, next):
        self.next = next
        
    def get_train_id(self):
        return self.train_id
        
    def get_next(self):
        return self.next

class Queue:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0

    def is_empty(self):
        return self.size == 0

    def push(self, train_id):
        newNode = TrainNode(train_id)
        if self.tail is None:
            self.head = newNode
            self.tail = newNode
        else:
            self.tail.set_next(newNode)
            self.tail = newNode
        self.size += 1

    def pop(self):
        if self.is_empty():
            return None
        remove_train_id = self.head.get_train_id()
        self.head = self.head.get_next()
        if self.head is None:
            self.tail = None
        self.size -= 1
        return remove_train_id

    # Helper to display the queue in HTML
    def get_all_items(self):
        items = []
        current = self.head
        while current:
            items.append(current.get_train_id())
            current = current.get_next()
        return items

# --- MERGE SORT ALGORITHM (Generic) ---
# Used for BOTH Daily (sorting logs by count) and Weekly (sorting days by average)
def merge_sort(data_list, key_func):
    """
    data_list: The list to sort
    key_func: A function to extract the value to compare (e.g., passenger count)
    """
    if len(data_list) <= 1:
        return data_list

    mid = len(data_list) // 2
    left = merge_sort(data_list[:mid], key_func)
    right = merge_sort(data_list[mid:], key_func)

    return merge(left, right, key_func)

def merge(left, right, key_func):
    result = []
    i = j = 0
    # Sort Descending (Highest to Lowest)
    while i < len(left) and j < len(right):
        # We use key_func to get the comparison value
        val_left = key_func(left[i])
        val_right = key_func(right[j])

        if val_left >= val_right: 
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    
    result.extend(left[i:])
    result.extend(right[j:])
    return result

# --- LINEAR SEARCH ALGORITHM ---
# Used for searching/filtering specific items in a list
def linear_search(data_list, search_term, attribute_func):
    """
    data_list: The list to search through
    search_term: The string to find
    attribute_func: Function to get the string attribute from the item
    """
    results = []
    if not search_term:
        return data_list

    search_term = str(search_term).lower()
    
    for item in data_list:
        # Check if attribute_func returns a value, handle None safely
        val = attribute_func(item)
        if val and search_term in str(val).lower():
            results.append(item)
            
    return results