
interface User {
    id: number;
    name: string;
}

async function fetchUsers(): Promise<User[]> {
    // TODO: Implement API call
    return [];
}

class UserService {
    private users: User[] = [];
    
    addUser(user: User): void {
        this.users.push(user);
    }
}
