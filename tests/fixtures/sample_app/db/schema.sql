CREATE TABLE events (
  id INT PRIMARY KEY,
  name VARCHAR(255),
  status ENUM('draft','open','closed')
);
CREATE TABLE tickets (
  id INT PRIMARY KEY,
  event_id INT,
  state VARCHAR(20),
  FOREIGN KEY (event_id) REFERENCES events(id)
);
CREATE TABLE event_tags (
  event_id INT,
  tag_id INT,
  FOREIGN KEY (event_id) REFERENCES events(id),
  FOREIGN KEY (tag_id) REFERENCES tags(id)
);
