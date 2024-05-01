import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
from adjustText import adjust_text


def create_map_window():
    # Create the main window
    root = tk.Tk()
    root.title("Game Map")

    # Create a matplotlib figure
    fig = Figure(figsize=(8, 8), dpi=100)
    ax = fig.add_subplot(111)

    # Generate random points
    np.random.seed(44)
    num_points = 10
    x = np.random.rand(num_points) * 200
    y = np.random.rand(num_points) * 200
    labels = [f"Location {i + 1}" for i in range(num_points)]

    # Plot points
    ax.scatter(x, y, marker='o')

    # Set plot limits
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 200)

    # Add labels using adjustText
    texts = [ax.text(x[i], y[i], labels[i], ha='center', va='center') for i in range(num_points)]
    adjust_text(texts, x=x, y=y)

    ax.tick_params(top=False, bottom=False, left=False, right=False,
                   labelleft=False, labelbottom=False)

    # Embed the figure in the tkinter window
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    # Function to handle key press
    def on_key_press(event):
        if event.char == 'q' or event.char == 'Q':
            root.quit()
            root.destroy()

    # Bind the key press event
    root.bind("<KeyPress>", on_key_press)

    # Start the GUI event loop
    root.mainloop()


# Function to show the map
create_map_window()
