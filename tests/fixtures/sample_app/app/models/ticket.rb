class Ticket < ApplicationRecord
  belongs_to :event
  # table_name 'tickets'
end
