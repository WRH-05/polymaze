import sys
from collections import deque

class API:
    """
    API class for communicating with micromouse simulator via stdin/stdout
    This works with simulators like MMS (mackorone/mms) and similar
    """
    
    @staticmethod
    def command(cmd):
        """Send a command to the simulator and return response if expected"""
        print(cmd, flush=True)
    
    @staticmethod
    def query(cmd):
        """Send a query command and return the response"""
        print(cmd, flush=True)
        response = input().strip()
        # Handle case where simulator sends acknowledgments
        while response in ['ack', 'reset']:
            response = input().strip()
        return response
    
    @staticmethod
    def mazeWidth():
        return int(API.query("mazeWidth"))
    
    @staticmethod
    def mazeHeight():
        return int(API.query("mazeHeight"))
    
    @staticmethod
    def wallFront():
        return API.query("wallFront") == "true"
    
    @staticmethod
    def wallRight():
        return API.query("wallRight") == "true"
    
    @staticmethod
    def wallLeft():
        return API.query("wallLeft") == "true"
    
    @staticmethod
    def wallBack():
        return API.query("wallBack") == "true"
    
    @staticmethod
    def moveForward(distance=1):
        API.command(f"moveForward {distance}")
    
    @staticmethod
    def turnRight():
        API.command("turnRight")
    
    @staticmethod
    def turnLeft():
        API.command("turnLeft")
    
    @staticmethod
    def setWall(x, y, direction):
        API.command(f"setWall {x} {y} {direction}")
    
    @staticmethod
    def clearWall(x, y, direction):
        API.command(f"clearWall {x} {y} {direction}")
    
    @staticmethod
    def setColor(x, y, color):
        API.command(f"setColor {x} {y} {color}")
    
    @staticmethod
    def clearColor(x, y):
        API.command(f"clearColor {x} {y}")
    
    @staticmethod
    def clearAllColor():
        API.command("clearAllColor")
    
    @staticmethod
    def setText(x, y, text):
        API.command(f"setText {x} {y} {text}")
    
    @staticmethod
    def clearText(x, y):
        API.command(f"clearText {x} {y}")
    
    @staticmethod
    def clearAllText():
        API.command("clearAllText")
    
    @staticmethod
    def wasReset():
        return API.query("wasReset") == "true"
    
    @staticmethod
    def ackReset():
        API.command("ackReset")

class MicromouseFloodfill:
    def __init__(self):
        self.width = API.mazeWidth()
        self.height = API.mazeHeight()
        
        # Robot state
        self.x = 0
        self.y = 0
        self.direction = 0  # 0=North, 1=East, 2=South, 3=West
        
        # Maze representation
        # walls[x][y] stores walls as bits: North=1, East=2, South=4, West=8
        self.walls = [[0 for _ in range(self.height)] for _ in range(self.width)]
        
        # Floodfill values
        self.flood_values = [[0 for _ in range(self.height)] for _ in range(self.width)]
        
        # Goal positions (center of maze)
        self.goals = []
        center_x = self.width // 2
        center_y = self.height // 2
        
        # Handle even/odd maze sizes for center goals
        if self.width % 2 == 0 and self.height % 2 == 0:
            self.goals = [(center_x-1, center_y-1), (center_x, center_y-1), 
                         (center_x-1, center_y), (center_x, center_y)]
        elif self.width % 2 == 0:
            self.goals = [(center_x-1, center_y), (center_x, center_y)]
        elif self.height % 2 == 0:
            self.goals = [(center_x, center_y-1), (center_x, center_y)]
        else:
            self.goals = [(center_x, center_y)]
        
        # Initialize maze boundaries
        self.initialize_boundaries()
        
        # Phase tracking
        self.phase = "explore"  # "explore" or "speed_run"
        self.visited = set()
        self.visited.add((0, 0))
        
        # Log initial state
        self.log(f"Maze size: {self.width}x{self.height}")
        self.log(f"Goals: {self.goals}")
    
    def log(self, message):
        """Log message to stderr for debugging"""
        print(message, file=sys.stderr, flush=True)
    
    def initialize_boundaries(self):
        """Initialize outer walls of the maze"""
        for x in range(self.width):
            self.walls[x][0] |= 4  # South wall
            self.walls[x][self.height-1] |= 1  # North wall
        
        for y in range(self.height):
            self.walls[0][y] |= 8  # West wall
            self.walls[self.width-1][y] |= 2  # East wall
    
    def get_direction_bit(self, direction):
        """Convert direction to wall bit"""
        return 1 << direction
    
    def is_wall(self, x, y, direction):
        """Check if there's a wall in given direction from position (x,y)"""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return True
        return bool(self.walls[x][y] & self.get_direction_bit(direction))
    
    def set_wall(self, x, y, direction):
        """Set a wall in the maze representation"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.walls[x][y] |= self.get_direction_bit(direction)
            
            # Set corresponding wall on adjacent cell
            dx, dy = self.get_direction_offset(direction)
            adj_x, adj_y = x + dx, y + dy
            if 0 <= adj_x < self.width and 0 <= adj_y < self.height:
                opposite_dir = (direction + 2) % 4
                self.walls[adj_x][adj_y] |= self.get_direction_bit(opposite_dir)
    
    def get_direction_offset(self, direction):
        """Get x,y offset for a direction"""
        offsets = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # N, E, S, W
        return offsets[direction]
    
    def scan_walls(self):
        """Scan for walls around current position"""
        # Check all four directions relative to robot's current orientation
        directions = [0, 1, 2, 3]  # Front, Right, Back, Left relative to robot
        wall_checks = [API.wallFront(), API.wallRight(), API.wallBack(), API.wallLeft()]
        
        for i, has_wall in enumerate(wall_checks):
            if has_wall:
                # Convert relative direction to absolute direction
                abs_direction = (self.direction + directions[i]) % 4
                self.set_wall(self.x, self.y, abs_direction)
                API.setWall(self.x, self.y, 'nsew'[abs_direction])
    
    def floodfill(self):
        """Perform floodfill algorithm to calculate distances to goal"""
        # Initialize all cells to max value
        for x in range(self.width):
            for y in range(self.height):
                self.flood_values[x][y] = float('inf')
        
        # Set goal cells to 0
        queue = deque()
        for goal_x, goal_y in self.goals:
            self.flood_values[goal_x][goal_y] = 0
            queue.append((goal_x, goal_y))
        
        # Flood fill
        while queue:
            x, y = queue.popleft()
            current_value = self.flood_values[x][y]
            
            # Check all four directions
            for direction in range(4):
                if not self.is_wall(x, y, direction):
                    dx, dy = self.get_direction_offset(direction)
                    next_x, next_y = x + dx, y + dy
                    
                    if (0 <= next_x < self.width and 0 <= next_y < self.height and
                        self.flood_values[next_x][next_y] > current_value + 1):
                        self.flood_values[next_x][next_y] = current_value + 1
                        queue.append((next_x, next_y))
        
        # Display flood values
        self.display_flood_values()
    
    def display_flood_values(self):
        """Display flood fill values in simulator"""
        API.clearAllText()
        for x in range(self.width):
            for y in range(self.height):
                if self.flood_values[x][y] != float('inf'):
                    API.setText(x, y, str(int(self.flood_values[x][y])))
    
    def get_best_direction(self):
        """Get the direction with lowest flood fill value"""
        current_value = self.flood_values[self.x][self.y]
        best_direction = None
        best_value = float('inf')
        
        for direction in range(4):
            if not self.is_wall(self.x, self.y, direction):
                dx, dy = self.get_direction_offset(direction)
                next_x, next_y = self.x + dx, self.y + dy
                
                if (0 <= next_x < self.width and 0 <= next_y < self.height):
                    next_value = self.flood_values[next_x][next_y]
                    if next_value < best_value:
                        best_value = next_value
                        best_direction = direction
        
        return best_direction
    
    def turn_to_direction(self, target_direction):
        """Turn robot to face target direction"""
        while self.direction != target_direction:
            diff = (target_direction - self.direction) % 4
            if diff == 1:  # Turn right
                API.turnRight()
                self.direction = (self.direction + 1) % 4
            elif diff == 3:  # Turn left
                API.turnLeft()
                self.direction = (self.direction - 1) % 4
            elif diff == 2:  # Turn around
                API.turnRight()
                API.turnRight()
                self.direction = (self.direction + 2) % 4
    
    def move_forward(self):
        """Move robot forward one cell"""
        API.moveForward()
        dx, dy = self.get_direction_offset(self.direction)
        self.x += dx
        self.y += dy
        self.visited.add((self.x, self.y))
        self.log(f"Moved to ({self.x}, {self.y})")
    
    def at_goal(self):
        """Check if robot is at any goal position"""
        return (self.x, self.y) in self.goals
    
    def should_explore_more(self):
        """Determine if we should continue exploring"""
        if self.phase == "speed_run":
            return False
        
        # Continue exploring if we haven't been everywhere accessible
        current_value = self.flood_values[self.x][self.y]
        
        # Check if we can reach an unexplored area
        for direction in range(4):
            if not self.is_wall(self.x, self.y, direction):
                dx, dy = self.get_direction_offset(direction)
                next_x, next_y = self.x + dx, self.y + dy
                
                if (0 <= next_x < self.width and 0 <= next_y < self.height and
                    (next_x, next_y) not in self.visited):
                    return True
        
        # If we're at the goal and have explored significantly, switch to speed run
        if self.at_goal() and len(self.visited) > (self.width * self.height) * 0.7:
            return False
        
        return len(self.visited) < (self.width * self.height) * 0.9
    
    def run(self):
        """Main algorithm loop"""
        API.setColor(0, 0, 'G')  # Mark start position
        
        # Mark goal positions
        for goal_x, goal_y in self.goals:
            API.setColor(goal_x, goal_y, 'R')
        
        step_count = 0
        while True:
            step_count += 1
            self.log(f"Step {step_count} at ({self.x}, {self.y}), phase: {self.phase}")
            
            # Handle reset
            if API.wasReset():
                self.log("Reset detected!")
                API.ackReset()
                # Reinitialize everything after reset
                self.x = 0
                self.y = 0
                self.direction = 0
                self.phase = "explore"
                self.visited = set()
                self.visited.add((0, 0))
                self.walls = [[0 for _ in range(self.height)] for _ in range(self.width)]
                self.initialize_boundaries()
                
                # Set goal positions back to center
                center_x = self.width // 2
                center_y = self.height // 2
                if self.width % 2 == 0 and self.height % 2 == 0:
                    self.goals = [(center_x-1, center_y-1), (center_x, center_y-1), 
                                 (center_x-1, center_y), (center_x, center_y)]
                elif self.width % 2 == 0:
                    self.goals = [(center_x-1, center_y), (center_x, center_y)]
                elif self.height % 2 == 0:
                    self.goals = [(center_x, center_y-1), (center_x, center_y)]
                else:
                    self.goals = [(center_x, center_y)]
                
                # Clear display and restart
                API.clearAllColor()
                API.clearAllText()
                API.setColor(0, 0, 'G')  # Mark start position
                for goal_x, goal_y in self.goals:
                    API.setColor(goal_x, goal_y, 'R')
                
                self.log("Reset complete, restarting algorithm")
                continue
            
            # Scan current position
            self.scan_walls()
            
            # Mark current position
            if self.phase == "explore":
                API.setColor(self.x, self.y, 'B')
            else:
                API.setColor(self.x, self.y, 'Y')
            
            # Update flood fill values
            self.floodfill()
            
            # Check if we've reached the goal
            if self.at_goal():
                if self.phase == "explore":
                    API.setColor(self.x, self.y, 'G')
                    self.log("Reached goal! Switching to speed run mode.")
                    self.phase = "speed_run"
                    # Return to start for speed run
                    self.goals = [(0, 0)]
                    continue
                elif self.phase == "speed_run":
                    API.setColor(self.x, self.y, 'G')
                    self.log("Speed run complete!")
                    break
            
            # Decide next move
            if self.should_explore_more() and self.phase == "explore":
                # Exploration phase - prioritize unvisited cells
                best_direction = None
                best_value = float('inf')
                
                for direction in range(4):
                    if not self.is_wall(self.x, self.y, direction):
                        dx, dy = self.get_direction_offset(direction)
                        next_x, next_y = self.x + dx, self.y + dy
                        
                        if 0 <= next_x < self.width and 0 <= next_y < self.height:
                            # Prioritize unvisited cells
                            if (next_x, next_y) not in self.visited:
                                next_value = self.flood_values[next_x][next_y] - 100
                            else:
                                next_value = self.flood_values[next_x][next_y]
                            
                            if next_value < best_value:
                                best_value = next_value
                                best_direction = direction
            else:
                # Speed run phase - follow optimal path
                best_direction = self.get_best_direction()
            
            if best_direction is not None:
                self.turn_to_direction(best_direction)
                self.move_forward()
            else:
                self.log("No valid moves available!")
                break
            
            # Safety check to prevent infinite loops
            if step_count > 10000:
                self.log("Maximum steps reached, terminating")
                break

# Create and run the micromouse
def main():
    try:
        mouse = MicromouseFloodfill()
        mouse.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()