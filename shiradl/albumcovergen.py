import os
import random

PATTERNS = {
	"dotgrid": lambda dotgrid_spacing: f"""
		<pattern id="dotgrid" width="{dotgrid_spacing}" height="{dotgrid_spacing}" patternUnits="userSpaceOnUse">
			<circle cx="{dotgrid_spacing/2}" cy="{dotgrid_spacing/2}" r="1" fill="#9C92AC" />
		</pattern>
	""",
	# credit: https://heropatterns.com
	"piefactory": lambda _: """
		<pattern id="piefactory" width="60" height="60" patternUnits="userSpaceOnUse">
			<g fill-rule="evenodd">
				<g fill="#9C92AC" fill-rule="nonzero" fill-opacity="0.3">
					<path d="M29 58.58l7.38-7.39A30.95 30.95 0 0 1 29 37.84a30.95 30.95 0 0 1-7.38 13.36l7.37 7.38zm1.4 1.41l.01.01h-2.84l-7.37-7.38A30.95 30.95 0 0 1 6.84 60H0v-1.02a28.9 28.9 0 0 0 18.79-7.78L0 32.41v-4.84L18.78 8.79A28.9 28.9 0 0 0 0 1.02V0h6.84a30.95 30.95 0 0 1 13.35 7.38L27.57 0h2.84l7.39 7.38A30.95 30.95 0 0 1 51.16 0H60v27.58-.01V60h-8.84a30.95 30.95 0 0 1-13.37-7.4L30.4 60zM29 1.41l-7.4 7.38A30.95 30.95 0 0 1 29 22.16 30.95 30.95 0 0 1 36.38 8.8L29 1.4zM58 1A28.9 28.9 0 0 0 39.2 8.8L58 27.58V1.02zm-20.2 9.2A28.9 28.9 0 0 0 30.02 29h26.56L37.8 10.21zM30.02 31a28.9 28.9 0 0 0 7.77 18.79l18.79-18.79H30.02zm9.18 20.2A28.9 28.9 0 0 0 58 59V32.4L39.2 51.19zm-19-1.4a28.9 28.9 0 0 0 7.78-18.8H1.41l18.8 18.8zm7.78-20.8A28.9 28.9 0 0 0 20.2 10.2L1.41 29h26.57z" />
				</g>
			</g>
		</pattern>
	""",
	# credit: https://heropatterns.com
	"graphpaper": lambda _: """
		<pattern id="graphpaper" width="100" height="100" patternUnits="userSpaceOnUse">
			<g fill-rule="evenodd">
				<g fill="#9C92AC" fill-opacity="0.4">
					<path opacity=".5" d="M96 95h4v1h-4v4h-1v-4h-9v4h-1v-4h-9v4h-1v-4h-9v4h-1v-4h-9v4h-1v-4h-9v4h-1v-4h-9v4h-1v-4h-9v4h-1v-4h-9v4h-1v-4H0v-1h15v-9H0v-1h15v-9H0v-1h15v-9H0v-1h15v-9H0v-1h15v-9H0v-1h15v-9H0v-1h15v-9H0v-1h15v-9H0v-1h15V0h1v15h9V0h1v15h9V0h1v15h9V0h1v15h9V0h1v15h9V0h1v15h9V0h1v15h9V0h1v15h9V0h1v15h4v1h-4v9h4v1h-4v9h4v1h-4v9h4v1h-4v9h4v1h-4v9h4v1h-4v9h4v1h-4v9h4v1h-4v9zm-1 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-9-10h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm9-10v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-9-10h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm9-10v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-9-10h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm9-10v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-10 0v-9h-9v9h9zm-9-10h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9zm10 0h9v-9h-9v9z" /><path d="M6 5V0H5v5H0v1h5v94h1V6h94V5H6z" />
				</g>
			</g>
		</pattern>
	""",
	# credit: https://heropatterns.com
	"plus": lambda _: """
		<pattern id="plus" width="60" height="60" patternUnits="userSpaceOnUse">
			<g fill="none" fill-rule="evenodd">
				<g fill="#9C92AC" fill-opacity="0.4">
					<path d="M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z"/>
				</g>
			</g>
		</pattern>
	"""
}
PATTERN_NAMES = ["dotgrid", "piefactory", "graphpaper", "plus"]

def generate_svg(
	width=500,
	height=500,
	circle2_radius=180,
	circle3_radius=100,
	circle4_radius=40,
	pattern_type="dotgrid",
	dotgrid_spacing=10,
	diag1_visible=True,
	diag2_visible=True,
	diag3_visible=True,
	diag4_visible=True,
):
	"""Generate SVG string with specified parameters"""

	min_distance = round(width / 16)
	
	if circle2_radius <= circle3_radius + min_distance:
		circle2_radius = circle3_radius + min_distance
	if circle3_radius <= circle4_radius + min_distance:
		circle3_radius = circle4_radius + min_distance

	diagonals = []
	if diag1_visible:
		diagonals.append(f'<line id="diag1" x1="1.5" y1="1.5" x2="{width/2}" y2="{height/2}" stroke="#a3a5aa" stroke-width="3" />')
	if diag2_visible:
		diagonals.append(f'<line id="diag2" x1="{width/2}" y1="{height/2}" x2="{width-1.5}" y2="{height-1.5}" stroke="#a3a5aa" stroke-width="3" />')
	if diag3_visible:
		diagonals.append(f'<line id="diag3" x1="{width-1.5}" y1="1.5" x2="{width/2}" y2="{height/2}" stroke="#a3a5aa" stroke-width="3" />')
	if diag4_visible:
		diagonals.append(f'<line id="diag4" x1="{width/2}" y1="{height/2}" x2="1.5" y2="{height-1.5}" stroke="#a3a5aa" stroke-width="3" />')
	
	diagonal_str = "\n            ".join(diagonals)


	return f"""
		<svg id="mainSvg" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
			<defs>
				{PATTERNS[pattern_type](dotgrid_spacing)}
			</defs>
			<rect id="outerRect" x="1.5" y="1.5" width="{width - 1.5}" height="{height - 1.5}" fill="black" stroke="#a3a5aa" stroke-width="3" />
			<circle id="circle1" cx="{width/2}" cy="{height/2}" r="{(min(width, height) - 3) / 2}" fill="none" stroke="#a3a5aa" stroke-width="3" />
			<circle id="circle2" cx="{width/2}" cy="{height/2}" r="{circle2_radius}" fill="none" stroke="#a3a5aa" stroke-width="3" />
			
			<!-- Pattern fill between circle 2 and circle 3 -->
			<mask id="patternMask">
				<rect width="{width}" height="{height}" fill="black" />
				<!-- PYTHON_REPLACE_MASKCIRCLE2_RADIUS:180 -->
				<circle id="maskCircle2" cx="{width/2}" cy="{height/2}" r="{circle2_radius}" fill="white" />
				<!-- PYTHON_REPLACE_MASKCIRCLE3_RADIUS:100 -->
				<circle id="maskCircle3" cx="{width/2}" cy="{height/2}" r="{circle3_radius}" fill="black" />
			</mask>

			<mask id="patternMask">
				<circle cx="{width/2}" cy="{height/2}" r="{circle2_radius}" fill="white" />
				<circle cx="{width/2}" cy="{height/2}" r="{circle3_radius}" fill="black" />
			</mask>
			<rect id="patternFill" width="{width}" height="{height}" fill="url(#{pattern_type})" mask="url(#patternMask)" />
			
			<circle id="circle3" cx="{width/2}" cy="{height/2}" r="{circle3_radius}" fill="black" stroke="#a3a5aa" stroke-width="3" />
			<circle id="circle4" cx="{width/2}" cy="{height/2}" r="{circle4_radius}" fill="none" stroke="#a3a5aa" stroke-width="3" />
			
			{diagonal_str}
		</svg>
	"""

def randomize_svg(seed=None, width=500, height=500):
	"""Randomize SVG parameters with given seed"""
	if seed is not None:
		random.seed(seed)

	offset = round(width / 20)
	offset2 = round(width / 7)

	# Generate c4 first (smallest)
	c4 = random.randint(offset, offset+offset2)
	# Generate c3 with minimum distance from c4
	c3_min = c4 + offset
	c3_max = 2*offset2
	c3 = random.randint(c3_min, min(c3_max, 2*offset2))
	# Generate c2 with minimum distance from c3
	c2_min = c3 + offset
	c2_max = 3*offset2
	c2 = random.randint(c2_min, min(c2_max, 3*offset2))
	
	pattern = random.choice(PATTERN_NAMES)
	dotgrid_spacing = 10
	if pattern == "dotgrid":
		# Randomize dotgrid spacing from default to 2x as spacious
		dotgrid_spacing = random.randint(round(width/50), round(width/25))
	
	# Randomize diagonal visibility
	diag1 = random.choice([True, False])
	diag2 = random.choice([True, False])
	diag3 = random.choice([True, False])
	diag4 = random.choice([True, False])
	
	return generate_svg(width, height, c2, c3, c4, pattern, dotgrid_spacing, diag1, diag2, diag3, diag4)

def get_unique_filename(filepath):
	"""Get a unique filename by adding/incrementing suffix if file exists"""
	if not os.path.exists(filepath):
		return filepath
	
	base, ext = os.path.splitext(filepath)
	counter = 1
	while os.path.exists(f"{base}_{counter}{ext}"):
		counter += 1
	return f"{base}_{counter}{ext}"

def render_svg_to_image(svg_string, output_path, format="jpeg"):
	"""Render SVG to image file"""
	try:
		import io

		from cairosvg import svg2png
		from PIL import Image
		
		# Convert SVG to PNG bytes
		png_bytes = svg2png(bytestring=svg_string.encode("utf-8"))
		
		# Open with PIL and convert to desired format
		img = Image.open(io.BytesIO(png_bytes))
		
		# Convert to RGB if necessary (for JPEG)
		if format.lower() in ["jpeg", "jpg"]:
			img = img.convert("RGB")
		
		# Save with appropriate format
		img.save(output_path, format=format.upper())
		
	except ImportError:
		# Fallback: save as SVG if dependencies not available
		with open(output_path.replace(".jpg", ".svg").replace(".jpeg", ".svg").replace(".png", ".svg"), "w") as f:
			f.write(svg_string)
		print("Note: cairosvg and PIL not available. Saved as SVG instead.")

def main(seed=None, width=500, height=500, output_format="jpeg", output_path="out.jpg"):
	"""Main function to generate and save randomized SVG"""
	# Generate randomized SVG
	svg_content = randomize_svg(seed, width, height)
	
	# Get unique output path
	unique_output_path = get_unique_filename(output_path)
	
	# Render and save
	render_svg_to_image(svg_content, unique_output_path, output_format)
	
	print(f"Generated image saved to: {unique_output_path}")

if __name__ == "__main__":
	import sys
	
	# Parse command line arguments
	seed = None
	width = 600
	height = 600
	output_format = "jpeg"
	output_path = "out.jpg"
	
	args = sys.argv[1:]
	if len(args) >= 1:
		seed = args[0]
	if len(args) >= 2:
		try:
			width = int(args[1])
			height = width  # Assume square
		except ValueError:
			pass
	if len(args) >= 3:
		try:
			height = int(args[2])
		except ValueError:
			pass
	if len(args) >= 4:
		output_format = args[3]
	if len(args) >= 5:
		output_path = args[4]
	
	main(seed, width, height, output_format, output_path)