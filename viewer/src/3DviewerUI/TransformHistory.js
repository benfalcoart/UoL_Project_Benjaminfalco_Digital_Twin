//Stores object transforms for undo and redo:
export class TransformHistory {
    //Create the undo and redo stacks:
    constructor() {
        this.undoStack = []
        this.redoStack = []
        this.startState = null
    }

    //Save the transform before an edit begins:
    begin(object) {
        this.startState = this.capture(object)
    }

    //Save the completed transform when it changed:
    end(object) {
        if (!object || !this.startState) {
            return
        }

        const endState = this.capture(object)

        if (!this.equal(this.startState, endState)) {
            this.undoStack.push(this.startState)
            this.redoStack.length = 0
        }

        this.startState = null
    }

    //Copy the current transform of an object:
    capture(object) {
        return {
            object,
            position: object.position.clone(),
            quaternion: object.quaternion.clone(),
            scale: object.scale.clone()
        }
    }

    //Restore a previously saved transform:
    restore(state) {
        state.object.position.copy(state.position)
        state.object.quaternion.copy(state.quaternion)
        state.object.scale.copy(state.scale)
        state.object.updateMatrixWorld(true)
    }

    //Check if two saved transforms are the same:
    equal(a, b) {
        return (
            a.position.equals(b.position) &&
            a.quaternion.equals(b.quaternion) &&
            a.scale.equals(b.scale)
        )
    }

    //Restore the previous transform:
    undo() {
        if (this.undoStack.length === 0) {
            return null
        }

        const action = this.undoStack.pop()
        this.redoStack.push(this.capture(action.object))
        this.restore(action)

        return action.object
    }

    //Restore the next transform:
    redo() {
        if (this.redoStack.length === 0) {
            return null
        }

        const action = this.redoStack.pop()
        this.undoStack.push(this.capture(action.object))
        this.restore(action)

        return action.object
    }
}