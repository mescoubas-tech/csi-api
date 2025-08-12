from fastapi import FastAPI
app = FastAPI()
@app.get('/')
async def root():
    return {'message': 'CSI API v1.5.0'}
